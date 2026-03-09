from __future__ import annotations

from fulcrum_trust.rlm.context import externalize_context
from fulcrum_trust.rlm.fixtures import generate_gratitude_loop_fixture
from fulcrum_trust.rlm.prototype import (
    DEFAULT_OBJECTIVE,
    RLMPrototype,
    score_gratitude_signal,
)
from fulcrum_trust.rlm.runtime import RLMRuntime


def test_runtime_executes_navigation_program_and_updates_answer() -> None:
    fixture = generate_gratitude_loop_fixture(
        target_tokens=24_000, pattern_position=0.5
    )
    context = externalize_context(fixture.history, session_id="runtime")
    runtime = RLMRuntime(context)
    program = RLMPrototype().build_navigation_program()

    trace = runtime.execute(
        program,
        objective=DEFAULT_OBJECTIVE,
        detector=score_gratitude_signal,
    )

    assert trace.answer["ready"] is True
    assert "Detected gratitude loop" in str(trace.answer["content"])
    assert trace.analysis_steps == (
        "sample-middle-band",
        "batch-score-handles",
        "mutate-answer",
    )
    assert trace.inspected_handles
    assert trace.evidence
