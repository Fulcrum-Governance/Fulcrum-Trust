from __future__ import annotations

from fulcrum_trust import RLMPrototype
from fulcrum_trust.rlm.fixtures import generate_gratitude_loop_fixture


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
