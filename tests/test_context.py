from __future__ import annotations

import asyncio

import pytest

from fulcrum_trust import TrustManager, TrustOutcome
from fulcrum_trust.context import (
    TrustEvaluationContext,
    get_current_context,
    reset_trust_context,
    set_trust_context,
)
from fulcrum_trust.evaluator import make_pair_id
from fulcrum_trust.types import TrustCircuitOpen


class TestContextFunctions:
    def test_default_context_is_none(self) -> None:
        assert get_current_context() is None

    def test_set_and_get_context(self) -> None:
        token = set_trust_context("agent_a|agent_b")
        try:
            ctx = get_current_context()
            assert ctx is not None
            assert ctx.pair_id == "agent_a|agent_b"
        finally:
            reset_trust_context(token)

    def test_reset_restores_none(self) -> None:
        token = set_trust_context("agent_a|agent_b")
        reset_trust_context(token)
        assert get_current_context() is None

    def test_nested_contexts(self) -> None:
        token1 = set_trust_context("pair_1")
        token2 = set_trust_context("pair_2")
        assert get_current_context().pair_id == "pair_2"
        reset_trust_context(token2)
        assert get_current_context().pair_id == "pair_1"
        reset_trust_context(token1)
        assert get_current_context() is None


class TestTrustEvaluationContext:
    def test_is_dataclass(self) -> None:
        ctx = TrustEvaluationContext(pair_id="test")
        assert ctx.pair_id == "test"


class TestContextIsolationConcurrent:
    @pytest.mark.asyncio
    async def test_concurrent_evaluations_no_cross_contamination(self) -> None:
        """Two concurrent asyncio tasks evaluating different pairs don't interfere."""
        manager = TrustManager()
        results: list[tuple[str, float]] = []

        async def eval_pair(a: str, b: str, outcome: TrustOutcome) -> None:
            state = manager.evaluate(a, b, outcome)
            results.append((make_pair_id(a, b), state.trust_score))

        await asyncio.gather(
            eval_pair("agent_x", "agent_y", TrustOutcome.SUCCESS),
            eval_pair("agent_p", "agent_q", TrustOutcome.FAILURE),
        )

        scores = {r[0]: r[1] for r in results}
        xy_pid = make_pair_id("agent_x", "agent_y")
        pq_pid = make_pair_id("agent_p", "agent_q")
        assert scores[xy_pid] > 0.5  # success -> trust above 0.5
        assert scores[pq_pid] < 0.5  # failure -> trust below 0.5


class TestRaiseOnBreak:
    def test_raise_on_break_true_raises_when_below_threshold(self) -> None:
        manager = TrustManager()
        # Drive trust down below threshold (0.3)
        manager.evaluate("a", "b", TrustOutcome.FAILURE)
        with pytest.raises(TrustCircuitOpen) as exc_info:
            manager.evaluate("a", "b", TrustOutcome.FAILURE, raise_on_break=True)
        assert exc_info.value.trust_score < 0.3
        assert exc_info.value.threshold == pytest.approx(0.3)

    def test_raise_on_break_false_never_raises(self) -> None:
        manager = TrustManager()
        manager.evaluate("a", "b", TrustOutcome.FAILURE)
        manager.evaluate("a", "b", TrustOutcome.FAILURE)
        # Default raise_on_break=False — should NOT raise even with low trust
        state = manager.evaluate("a", "b", TrustOutcome.FAILURE)
        assert state.trust_score < 0.3  # trust is below threshold
        # No exception raised

    def test_raise_on_break_true_does_not_raise_when_above_threshold(self) -> None:
        manager = TrustManager()
        # Trust above threshold — should not raise
        state = manager.evaluate("a", "b", TrustOutcome.SUCCESS, raise_on_break=True)
        assert state.trust_score > 0.3

    def test_context_cleaned_up_even_when_raising(self) -> None:
        """Context is restored to None even when TrustCircuitOpen is raised."""
        manager = TrustManager()
        manager.evaluate("a", "b", TrustOutcome.FAILURE)
        try:
            manager.evaluate("a", "b", TrustOutcome.FAILURE, raise_on_break=True)
        except TrustCircuitOpen:
            pass
        assert get_current_context() is None
