from __future__ import annotations

import asyncio
import pytest
from typing import Any, Dict, List
from typing_extensions import TypedDict

from fulcrum_trust import TrustConfig, TrustManager, TrustOutcome, TrustState
from fulcrum_trust.adapters.langgraph import OutcomeClassifier, TrustAwareGraph
from langgraph.graph import END, StateGraph


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


class SimpleState(TypedDict):
    value: str
    count: int


@pytest.fixture
def simple_builder() -> StateGraph:
    """Two-node graph: inc_count -> set_value -> END. No LLM."""
    builder = StateGraph(SimpleState)
    builder.add_node("inc_count", lambda s: {"count": s["count"] + 1})
    builder.add_node("set_value", lambda s: {"value": "done"})
    builder.add_edge("__start__", "inc_count")
    builder.add_edge("inc_count", "set_value")
    builder.add_edge("set_value", END)
    return builder


@pytest.fixture
def trust_manager() -> TrustManager:
    return TrustManager()


# ---------------------------------------------------------------------------
# class TestOutcomeClassifier
# ---------------------------------------------------------------------------


class TestOutcomeClassifier:
    """Unit tests for OutcomeClassifier.classify() — one test per branch."""

    def setup_method(self) -> None:
        self.clf = OutcomeClassifier()

    def test_classify_none_output_returns_failure(self) -> None:
        result = self.clf.classify({}, None)
        assert result == TrustOutcome.FAILURE

    def test_classify_non_dict_output_returns_failure(self) -> None:
        result = self.clf.classify({}, "string")
        assert result == TrustOutcome.FAILURE

    def test_classify_empty_dict_returns_failure(self) -> None:
        result = self.clf.classify({"count": 0}, {})
        assert result == TrustOutcome.FAILURE

    def test_classify_error_key_returns_failure(self) -> None:
        result = self.clf.classify({}, {"error": "something went wrong"})
        assert result == TrustOutcome.FAILURE

    def test_classify_exception_key_returns_failure(self) -> None:
        result = self.clf.classify({}, {"exception": "RuntimeError"})
        assert result == TrustOutcome.FAILURE

    def test_classify_traceback_key_returns_failure(self) -> None:
        result = self.clf.classify({}, {"traceback": "..."})
        assert result == TrustOutcome.FAILURE

    def test_classify_identical_long_string_returns_partial(self) -> None:
        # A string longer than min_string_length_for_repetition (default 20) that is
        # unchanged constitutes repetitive output -> PARTIAL.
        long_msg = "x" * 30
        result = self.clf.classify({"msg": long_msg}, {"msg": long_msg})
        assert result == TrustOutcome.PARTIAL

    def test_classify_identical_numeric_value_returns_success(self) -> None:
        # Numeric repetition is NOT treated as PARTIAL — integers are not long strings
        # or non-empty collections. Validates Pitfall 6 fix from RESEARCH.md.
        result = self.clf.classify({"count": 5}, {"count": 5})
        assert result == TrustOutcome.SUCCESS

    def test_classify_valid_update_returns_success(self) -> None:
        result = self.clf.classify({"count": 0}, {"count": 1})
        assert result == TrustOutcome.SUCCESS

    def test_classify_new_key_not_in_prior_returns_success(self) -> None:
        result = self.clf.classify({}, {"result": "hello"})
        assert result == TrustOutcome.SUCCESS

    def test_classify_list_value_unchanged_returns_partial(self) -> None:
        # A non-empty list value that is unchanged constitutes repetition -> PARTIAL.
        items = [1, 2, 3]
        result = self.clf.classify({"items": items}, {"items": items})
        assert result == TrustOutcome.PARTIAL


# ---------------------------------------------------------------------------
# class TestTrustAwareGraph
# ---------------------------------------------------------------------------


class TestTrustAwareGraph:
    """Integration tests for TrustAwareGraph covering LANG-01 through LANG-04."""

    # ------------------------------------------------------------------
    # LANG-01: Zero-changes wrapping
    # ------------------------------------------------------------------

    def test_wrap_graph_runs_normally(self, simple_builder: StateGraph) -> None:
        """LANG-01: Wrapped graph produces correct final state end-to-end."""
        tm = TrustManager()
        wrapper = TrustAwareGraph(simple_builder, tm, agent_a="a", agent_b="b")
        compiled = wrapper.compile()
        result = compiled.invoke({"value": "start", "count": 0})
        assert result["count"] == 1
        assert result["value"] == "done"

    def test_wrap_preserves_node_count(self) -> None:
        """LANG-01: Wrapped graph produces same final state as unwrapped graph."""
        # Build two independent graphs from scratch to avoid fixture reuse.
        def make_builder() -> StateGraph:
            b = StateGraph(SimpleState)
            b.add_node("inc_count", lambda s: {"count": s["count"] + 1})
            b.add_node("set_value", lambda s: {"value": "done"})
            b.add_edge("__start__", "inc_count")
            b.add_edge("inc_count", "set_value")
            b.add_edge("set_value", END)
            return b

        unwrapped = make_builder().compile()
        wrapped = TrustAwareGraph(
            make_builder(), TrustManager(), agent_a="a", agent_b="b"
        ).compile()

        input_state: SimpleState = {"value": "", "count": 0}
        assert unwrapped.invoke(input_state) == wrapped.invoke(input_state)

    # ------------------------------------------------------------------
    # LANG-02: Outcome classification integration
    # ------------------------------------------------------------------

    def test_trust_score_increases_on_success_nodes(
        self, simple_builder: StateGraph
    ) -> None:
        """LANG-02: Successful node outputs improve trust score above 0.5."""
        tm = TrustManager()
        score_before = tm.get_trust_score("a", "b")  # 0.5 (uninformative prior)
        wrapper = TrustAwareGraph(simple_builder, tm, agent_a="a", agent_b="b")
        wrapper.compile().invoke({"value": "start", "count": 0})
        score_after = tm.get_trust_score("a", "b")
        assert score_after > score_before

    def test_trust_decreases_on_error_node(self) -> None:
        """LANG-02: Node returning error-keyed output decreases trust below 0.5."""
        builder = StateGraph(SimpleState)
        builder.add_node("bad_node", lambda s: {"error": "something failed"})
        builder.add_edge("__start__", "bad_node")
        builder.add_edge("bad_node", END)

        tm = TrustManager()
        wrapper = TrustAwareGraph(builder, tm, agent_a="a", agent_b="b")
        wrapper.compile().invoke({"value": "", "count": 0})
        assert tm.get_trust_score("a", "b") < 0.5

    # ------------------------------------------------------------------
    # LANG-03: Circuit-break graph termination
    # ------------------------------------------------------------------

    def test_circuit_break_terminates_graph(self, trust_manager: TrustManager) -> None:
        """LANG-03: Graph routes to END via conditional edge when trust is below
        threshold. step2 must NOT execute — this confirms hard termination, not
        merely callback emission."""
        tm = TrustManager(config=TrustConfig(threshold=0.9))
        for _ in range(5):
            tm.evaluate("a", "b", TrustOutcome.FAILURE)
        assert tm.should_terminate("a", "b")

        executed_step2: List[bool] = []

        builder = StateGraph(SimpleState)
        builder.add_node("step1", lambda s: {"count": s["count"] + 1})
        builder.add_node(
            "step2", lambda s: executed_step2.append(True) or {"value": "done"}
        )
        builder.add_edge("__start__", "step1")
        builder.add_edge("step1", "step2")
        builder.add_edge("step2", END)

        cb_fired: List[Any] = []
        wrapper = TrustAwareGraph(builder, tm, agent_a="a", agent_b="b")
        wrapper.on_circuit_break(lambda s: cb_fired.append(s))
        compiled = wrapper.compile()
        compiled.invoke({"value": "", "count": 0})

        assert len(cb_fired) > 0, "on_circuit_break never fired"
        assert len(executed_step2) == 0, (
            "step2 executed despite trust below threshold — termination failed"
        )

    def test_no_circuit_break_on_healthy_trust(
        self, simple_builder: StateGraph
    ) -> None:
        """LANG-03: No termination when trust is healthy (starts at 0.5, threshold 0.3)."""
        tm = TrustManager()  # threshold=0.3 (default), trust starts at 0.5
        cb_fired: List[Any] = []
        wrapper = TrustAwareGraph(simple_builder, tm, agent_a="a", agent_b="b")
        wrapper.on_circuit_break(lambda s: cb_fired.append(s))
        result = wrapper.compile().invoke({"value": "start", "count": 0})

        assert len(cb_fired) == 0, "on_circuit_break fired despite healthy trust"
        assert result["count"] == 1
        assert result["value"] == "done"

    # ------------------------------------------------------------------
    # LANG-04: Callbacks
    # ------------------------------------------------------------------

    def test_on_trust_change_fires_per_node(self, simple_builder: StateGraph) -> None:
        """LANG-04: on_trust_change fires exactly once per node (2 nodes -> 2 calls)."""
        tm = TrustManager()
        fired: List[Any] = []
        wrapper = TrustAwareGraph(simple_builder, tm, agent_a="a", agent_b="b")
        wrapper.on_trust_change(lambda s: fired.append(s))
        wrapper.compile().invoke({"value": "start", "count": 0})
        assert len(fired) == 2

    def test_on_circuit_break_callback_receives_trust_state(self) -> None:
        """LANG-04: on_circuit_break receives a TrustState with trust_score < 0.5."""
        tm = TrustManager(config=TrustConfig(threshold=0.9))
        for _ in range(5):
            tm.evaluate("a", "b", TrustOutcome.FAILURE)

        builder = StateGraph(SimpleState)
        builder.add_node("step1", lambda s: {"count": s["count"] + 1})
        builder.add_edge("__start__", "step1")
        builder.add_edge("step1", END)

        fired: List[Any] = []
        wrapper = TrustAwareGraph(builder, tm, agent_a="a", agent_b="b")
        wrapper.on_circuit_break(lambda s: fired.append(s))
        wrapper.compile().invoke({"value": "", "count": 0})

        assert len(fired) > 0
        assert isinstance(fired[0], TrustState)
        assert fired[0].trust_score < 0.5

    def test_on_recovery_fires_after_reset(self) -> None:
        """LANG-04: on_recovery fires when trust recovers above threshold after a break.

        Approach: pre-seed failures, invoke once to set _was_terminated=True on the
        wrapper, then reset the manager and invoke a fresh wrapper (compiled graphs are
        single-use) with _was_terminated pre-set to simulate the post-break state.
        """
        tm = TrustManager(config=TrustConfig(threshold=0.5))
        for _ in range(3):
            tm.evaluate("a", "b", TrustOutcome.FAILURE)
        assert tm.should_terminate("a", "b")

        # First invoke: circuit fires, establishes _was_terminated = True in the adapter.
        builder1 = StateGraph(SimpleState)
        builder1.add_node("step1", lambda s: {"count": s["count"] + 1})
        builder1.add_edge("__start__", "step1")
        builder1.add_edge("step1", END)
        cb1: List[Any] = []
        w1 = TrustAwareGraph(builder1, tm, agent_a="a", agent_b="b")
        w1.on_circuit_break(lambda s: cb1.append(True))
        w1.compile().invoke({"value": "", "count": 0})
        assert len(cb1) > 0, "circuit break did not fire during setup"

        # Reset trust: pair reverts to uninformative prior (trust_score = 0.5,
        # above threshold 0.5 is NOT below threshold, so should_terminate = False).
        tm.reset("a", "b")

        # Second invoke: fresh builder and wrapper. Pre-set _was_terminated=True so
        # the adapter treats this as a post-break recovery context.
        recovered: List[Any] = []
        builder2 = StateGraph(SimpleState)
        builder2.add_node("step1", lambda s: {"count": s["count"] + 1})
        builder2.add_edge("__start__", "step1")
        builder2.add_edge("step1", END)
        w2 = TrustAwareGraph(builder2, tm, agent_a="a", agent_b="b")
        w2._was_terminated = True  # simulate post-break state
        w2.on_recovery(lambda s: recovered.append(s))
        w2.compile().invoke({"value": "", "count": 0})

        assert len(recovered) >= 1, "on_recovery callback never fired"

    # ------------------------------------------------------------------
    # Async node support
    # ------------------------------------------------------------------

    def test_async_node_is_wrapped_correctly(self) -> None:
        """Async def nodes are wrapped with trust evaluation via the afunc path.

        LangGraph 0.4.x stores async nodes as afunc=<coroutine> with func=None on
        RunnableCallable. The wrapper detects afunc and wraps it so trust is updated
        after the async invocation. ainvoke is required for async-only nodes.
        """

        async def async_node(state: SimpleState) -> dict:
            return {"count": state["count"] + 10}

        builder = StateGraph(SimpleState)
        builder.add_node("async_step", async_node)
        builder.add_edge("__start__", "async_step")
        builder.add_edge("async_step", END)

        tm = TrustManager()

        async def run() -> Dict[str, Any]:
            wrapper = TrustAwareGraph(builder, tm, agent_a="a", agent_b="b")
            compiled = wrapper.compile()
            return await compiled.ainvoke({"value": "", "count": 0})  # type: ignore[no-any-return]

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result["count"] == 10
        assert tm.get_trust_score("a", "b") != 0.5, (
            "Trust score unchanged after async node — trust evaluation wrapper did not run"
        )

    # ------------------------------------------------------------------
    # Missing langgraph guard
    # ------------------------------------------------------------------

    def test_import_error_without_langgraph(
        self, simple_builder: StateGraph, trust_manager: TrustManager
    ) -> None:
        """ImportError is raised with pip install hint when langgraph unavailable."""
        import fulcrum_trust.adapters.langgraph as adapter_mod

        original = adapter_mod._LANGGRAPH_AVAILABLE
        adapter_mod._LANGGRAPH_AVAILABLE = False
        try:
            with pytest.raises(ImportError, match="pip install"):
                TrustAwareGraph(simple_builder, trust_manager)
        finally:
            adapter_mod._LANGGRAPH_AVAILABLE = original
