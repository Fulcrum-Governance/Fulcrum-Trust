from __future__ import annotations

from fulcrum_trust import RLMPrototype
from fulcrum_trust.rlm.fixtures import generate_gratitude_loop_fixture
from fulcrum_trust.rlm.types import BatchFinding


def _finding(handle: str = "ctx://s/0003") -> BatchFinding:
    return BatchFinding(
        handle=handle,
        score=7.5,
        excerpt="thank you ... grateful for the handoff",
        matches=("thank you", "grateful for the handoff"),
    )


def test_prototype_detects_middle_gratitude_loop_and_reports_tool_chain() -> None:
    fixture = generate_gratitude_loop_fixture(
        target_tokens=110_000, pattern_position=0.65
    )
    prototype = RLMPrototype()

    result = prototype.analyze(fixture.history, session_id="prototype")

    assert result.total_tokens >= 100_000
    assert result.prototype_detected is True
    assert result.baseline_detected is False
    assert result.answer["ready"] is True
    assert result.tool_chain == ("read", "analyze", "report")
    assert result.report.startswith("Detected gratitude loop")
    assert result.evidence
    assert result.inspected_handles


def test_benchmark_middle_position_recall_beats_baseline() -> None:
    prototype = RLMPrototype()

    benchmark = prototype.benchmark_middle_position_recall()

    assert benchmark.fixture_count == 5
    assert benchmark.prototype_accuracy == 1.0
    assert benchmark.baseline_accuracy < benchmark.prototype_accuracy
    assert all(case.prototype_detected for case in benchmark.cases)
    assert not any(case.baseline_detected for case in benchmark.cases)


def test_render_report_appends_handles_when_evidence_value_is_list() -> None:
    """A list of evidence handles is normalized to a tuple and appended."""
    prototype = RLMPrototype()
    answer = {
        "content": "Detected gratitude loop.",
        "evidence_handles": ["ctx://s/0003", "ctx://s/0004"],
    }

    report = prototype._render_report(answer, (_finding(),))

    assert report == (
        "Detected gratitude loop. Evidence handles: ctx://s/0003, ctx://s/0004."
    )


def test_render_report_ignores_non_sequence_evidence_value() -> None:
    """A non-tuple/non-list evidence value yields no handle suffix."""
    prototype = RLMPrototype()
    answer = {
        "content": "Detected gratitude loop.",
        "evidence_handles": "ctx://s/0003",  # a bare string, not a sequence of handles
    }

    report = prototype._render_report(answer, (_finding(),))

    # The string branch falls through to empty handles, so no suffix is appended.
    assert report == "Detected gratitude loop."


def test_render_report_returns_content_only_without_evidence() -> None:
    """With no evidence findings, only the answer content is returned."""
    prototype = RLMPrototype()
    answer = {
        "content": "No gratitude loop detected.",
        "evidence_handles": ["ctx://s/0003"],
    }

    report = prototype._render_report(answer, ())

    assert report == "No gratitude loop detected."


def test_render_report_returns_content_only_without_handles() -> None:
    """With evidence findings but no handles, only the content is returned."""
    prototype = RLMPrototype()
    answer = {"content": "Detected gratitude loop.", "evidence_handles": ()}

    report = prototype._render_report(answer, (_finding(),))

    assert report == "Detected gratitude loop."
