from __future__ import annotations

import asyncio
import functools
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

from fulcrum_trust.manager import TrustManager
from fulcrum_trust.types import TrustOutcome, TrustState

try:
    from langgraph.graph import StateGraph

    _LANGGRAPH_AVAILABLE = True
except ImportError:
    _LANGGRAPH_AVAILABLE = False

if TYPE_CHECKING:
    from langgraph.graph import StateGraph


def _make_routing_fn(
    trust_manager: TrustManager, agent_a: str, agent_b: str, normal_next: str
) -> Callable[[Any], str]:
    """Build a routing function for conditional edge injection.

    The returned function routes to ``"terminate"`` (END) when
    ``trust_manager.should_terminate()`` returns True for the given agent pair,
    and to ``"continue"`` (normal_next) otherwise.

    Defined at module level to avoid the B023 lint warning about closures that
    capture loop variables.

    Args:
        trust_manager: TrustManager instance for termination decisions.
        agent_a: First agent identifier.
        agent_b: Second agent identifier.
        normal_next: Normal destination node name when trust is healthy.

    Returns:
        A routing function suitable for use with ``add_conditional_edges``.
    """

    def routing_fn(state: Any) -> str:
        """Route to END if trust is below threshold, else continue normally."""
        if trust_manager.should_terminate(agent_a, agent_b):
            return "terminate"
        return "continue"

    return routing_fn


@dataclass
class CallbackRegistry:
    """Registry of callbacks fired on trust lifecycle events.

    All callbacks receive the current TrustState at the moment they fire.
    Callbacks are appended to the appropriate list and called in order.

    Attributes:
        on_trust_change: Called after every node evaluation, regardless of outcome.
        on_circuit_break: Called when trust drops below the termination threshold.
        on_recovery: Called when trust recovers above the threshold after a break.
    """

    on_trust_change: list[Callable[[TrustState], None]] = field(default_factory=list)
    on_circuit_break: list[Callable[[TrustState], None]] = field(default_factory=list)
    on_recovery: list[Callable[[TrustState], None]] = field(default_factory=list)

    def fire_trust_change(self, state: TrustState) -> None:
        """Fire all on_trust_change callbacks with the given TrustState.

        Args:
            state: Current trust state to pass to each callback.
        """
        for cb in self.on_trust_change:
            cb(state)

    def fire_circuit_break(self, state: TrustState) -> None:
        """Fire all on_circuit_break callbacks with the given TrustState.

        Args:
            state: Current trust state to pass to each callback.
        """
        for cb in self.on_circuit_break:
            cb(state)

    def fire_recovery(self, state: TrustState) -> None:
        """Fire all on_recovery callbacks with the given TrustState.

        Args:
            state: Current trust state to pass to each callback.
        """
        for cb in self.on_recovery:
            cb(state)


class OutcomeClassifier:
    """Classifies node outputs into TrustOutcome values for trust evaluation.

    Uses heuristics to distinguish successful outputs, partial/repetitive
    outputs, and failure outputs (None, empty, error-keyed, or unchanged).

    Attributes:
        ERROR_KEYS: Frozenset of dict keys that signal an error output.
    """

    ERROR_KEYS: frozenset[str] = frozenset({"error", "exception", "traceback"})

    def __init__(self, min_string_length_for_repetition: int = 20) -> None:
        """Initialise the classifier.

        Args:
            min_string_length_for_repetition: Minimum string value length required
                before an unchanged value is treated as repetitive (PARTIAL). Prevents
                false-positive PARTIAL classification on short IDs or numeric counters.
        """
        self._min_string_length = min_string_length_for_repetition

    def classify(self, prior_state: Any, node_output: Any) -> TrustOutcome:
        """Classify a node's output as SUCCESS, PARTIAL, or FAILURE.

        Classification rules (applied in order):
        1. None output -> FAILURE
        2. Non-dict output -> FAILURE
        3. Empty dict output -> FAILURE
        4. Dict containing any ERROR_KEYS -> FAILURE
        5. All overlapping values unchanged AND at least one is a long string or
           non-empty collection (repetition check, only when prior_state is dict) -> PARTIAL
        6. Default -> SUCCESS

        Args:
            prior_state: State passed into the node before execution.
            node_output: Value returned by the node callable.

        Returns:
            TrustOutcome classification for the output.
        """
        if node_output is None:
            return TrustOutcome.FAILURE

        if not isinstance(node_output, dict):
            return TrustOutcome.FAILURE

        if not node_output:
            return TrustOutcome.FAILURE

        if any(k in node_output for k in self.ERROR_KEYS):
            return TrustOutcome.FAILURE

        # Repetition check — only meaningful when prior state is also a dict.
        if isinstance(prior_state, dict):
            overlapping_keys = set(node_output) & set(prior_state)
            if overlapping_keys:
                all_equal = all(
                    node_output[k] == prior_state[k] for k in overlapping_keys
                )
                if all_equal:
                    # At least one value must be a "substantive" type to qualify
                    # as repetitive: a string exceeding the minimum length threshold,
                    # or a non-empty list/dict.
                    has_substantive = any(
                        (
                            isinstance(node_output[k], str)
                            and len(node_output[k]) > self._min_string_length
                        )
                        or (
                            isinstance(node_output[k], (list, dict))
                            and len(node_output[k]) > 0
                        )
                        for k in overlapping_keys
                    )
                    if has_substantive:
                        return TrustOutcome.PARTIAL

        return TrustOutcome.SUCCESS


class TrustAwareGraph:
    """Wraps a LangGraph StateGraph with automatic trust evaluation at node boundaries.

    Intercepts each node execution, classifies the output, updates the trust
    engine, fires registered callbacks, and injects conditional edges so the
    compiled graph routes to END when trust falls below the configured threshold.

    Zero changes to user graph code are required: pass an uncompiled StateGraph
    and a TrustManager, register optional callbacks, then call compile().

    Args:
        graph: An uncompiled LangGraph StateGraph instance.
        trust_manager: TrustManager instance for evaluation and termination decisions.
        agent_a: Identifier for the first agent in the trust pair. Defaults to
            "orchestrator".
        agent_b: Identifier for the second agent in the trust pair. Defaults to
            "worker".

    Raises:
        ImportError: If langgraph is not installed.

    Example:
        >>> from langgraph.graph import StateGraph, END
        >>> from fulcrum_trust import TrustManager
        >>> builder = StateGraph(MyState)
        >>> builder.add_node("process", my_fn)
        >>> builder.add_edge("__start__", "process")
        >>> builder.add_edge("process", END)
        >>> wrapper = TrustAwareGraph(builder, TrustManager())
        >>> compiled = wrapper.compile()
    """

    def __init__(
        self,
        graph: StateGraph,
        trust_manager: TrustManager,
        agent_a: str = "orchestrator",
        agent_b: str = "worker",
    ) -> None:
        """Initialise the wrapper.

        Args:
            graph: Uncompiled StateGraph to wrap.
            trust_manager: TrustManager for evaluation and termination decisions.
            agent_a: First agent identifier in the trust pair.
            agent_b: Second agent identifier in the trust pair.

        Raises:
            ImportError: If langgraph is not installed.
        """
        if not _LANGGRAPH_AVAILABLE:
            raise ImportError(
                "langgraph is required for TrustAwareGraph. "
                "Install with: pip install 'fulcrum-trust[langgraph]'"
            )
        self._graph = graph
        self._trust_manager = trust_manager
        self._agent_a = agent_a
        self._agent_b = agent_b
        self._classifier = OutcomeClassifier()
        self._callbacks = CallbackRegistry()
        self._was_terminated = False

    def on_trust_change(self, callback: Callable[[TrustState], None]) -> None:
        """Register a callback that fires after every node evaluation.

        Args:
            callback: Callable accepting the current TrustState.
        """
        self._callbacks.on_trust_change.append(callback)

    def on_circuit_break(self, callback: Callable[[TrustState], None]) -> None:
        """Register a callback that fires when trust drops below the threshold.

        Args:
            callback: Callable accepting the current TrustState.
        """
        self._callbacks.on_circuit_break.append(callback)

    def on_recovery(self, callback: Callable[[TrustState], None]) -> None:
        """Register a callback that fires when trust recovers above the threshold.

        Args:
            callback: Callable accepting the current TrustState.
        """
        self._callbacks.on_recovery.append(callback)

    def _evaluate_and_route(self, prior_state: Any, result: Any) -> None:
        """Evaluate node output, update trust state, and fire appropriate callbacks.

        Args:
            prior_state: Graph state that was passed into the node.
            result: Output returned by the node callable.
        """
        outcome = self._classifier.classify(prior_state, result)
        trust_state = self._trust_manager.evaluate(
            self._agent_a, self._agent_b, outcome
        )
        self._callbacks.fire_trust_change(trust_state)
        is_terminated = self._trust_manager.should_terminate(
            self._agent_a, self._agent_b
        )
        if is_terminated:
            self._callbacks.fire_circuit_break(trust_state)
        if not is_terminated and self._was_terminated:
            self._callbacks.fire_recovery(trust_state)
        self._was_terminated = is_terminated

    def _make_node_wrapper(self, node_fn: Callable[[Any], Any]) -> Callable[[Any], Any]:
        """Wrap a node callable with trust evaluation logic.

        Detects whether the callable is async and produces the appropriate
        wrapper type so LangGraph's async runner is not broken.

        Args:
            node_fn: Original node callable (sync or async).

        Returns:
            Wrapped callable with identical signature that fires trust evaluation
            after each invocation.
        """
        if asyncio.iscoroutinefunction(node_fn):

            @functools.wraps(node_fn)
            async def async_wrapped(state: Any) -> Any:
                result = await node_fn(state)
                self._evaluate_and_route(state, result)
                return result

            return async_wrapped
        else:

            @functools.wraps(node_fn)
            def sync_wrapped(state: Any) -> Any:
                result = node_fn(state)
                self._evaluate_and_route(state, result)
                return result

            return sync_wrapped

    def _wrap_nodes(self) -> None:
        """Replace each node callable in the graph with a trust-evaluating wrapper.

        Supports two node layouts observed across LangGraph versions:

        - StateNodeSpec NamedTuple with ``.runnable.func`` (LangGraph 0.2+/0.4+):
          extracts the original callable, wraps it, creates a new RunnableCallable,
          and uses ``_replace()`` to produce an updated spec (NamedTuple is immutable).
        - Direct callable entry: wraps and assigns directly.

        The graph's ``nodes`` dict is mutated in place via a local ``Any`` alias to
        avoid mypy errors against LangGraph's internal types.
        """
        graph: Any = self._graph  # local Any alias for internal-API access
        for name, spec in list(graph.nodes.items()):
            if name == "__start__":
                continue
            runnable = getattr(spec, "runnable", None)
            original_fn: Callable[[Any], Any] | None = getattr(runnable, "func", None)
            if original_fn is not None:
                wrapped = self._make_node_wrapper(original_fn)
                # Build a replacement runnable. Prefer langgraph.utils.runnable.
                # RunnableCallable (native async/sync dispatch) over RunnableLambda.
                new_runnable: Any
                try:
                    from langgraph.utils.runnable import RunnableCallable

                    new_runnable = RunnableCallable(wrapped)
                except ImportError:
                    from langchain_core.runnables import RunnableLambda

                    new_runnable = RunnableLambda(wrapped)
                # StateNodeSpec is a NamedTuple; _replace() creates a new instance.
                new_spec = spec._replace(runnable=new_runnable)
                graph.nodes[name] = new_spec
            elif callable(spec):
                # Direct callable layout (rare, future-proofing).
                graph.nodes[name] = self._make_node_wrapper(spec)

    def _inject_termination_edges(self) -> None:
        """Inject conditional edges that route to END when trust is below threshold.

        For each non-__start__ node that has a simple outgoing edge, this method:
        1. Removes the simple edge from the graph's edge set.
        2. Adds a conditional edge routing to ``END`` (key ``"terminate"``) when
           ``should_terminate()`` is True, or to the original destination (key
           ``"continue"``) otherwise.

        Nodes with no simple outgoing edge (already conditional or terminal) are
        skipped. ``graph.edges`` is a ``set`` of ``(src, dst)`` tuples in LangGraph
        0.2+; the ``discard`` call is wrapped in a try/except for version resilience.
        """
        from langgraph.graph import END as _END

        graph: Any = self._graph  # local Any alias for internal-API access

        # Build source -> destination map from simple (non-conditional) edges.
        edge_map: dict[str, str] = {}
        for edge in graph.edges:
            src, dst = edge  # each element is a (str, str) tuple
            edge_map[src] = dst

        node_names = [n for n in graph.nodes if n != "__start__"]

        for node_name in node_names:
            normal_next = edge_map.get(node_name)
            if normal_next is None:
                # No simple outgoing edge (already conditional or terminal). Skip.
                continue

            routing_fn = _make_routing_fn(
                self._trust_manager, self._agent_a, self._agent_b, normal_next
            )

            # Remove the simple edge before adding the conditional one.
            try:
                graph.edges.discard((node_name, normal_next))
            except AttributeError:
                pass  # edges not a set in this LangGraph version — skip discard

            graph.add_conditional_edges(
                node_name,
                routing_fn,
                {"continue": normal_next, "terminate": _END},
            )

    def compile(self, **kwargs: Any) -> Any:
        """Wrap all nodes with trust evaluation and inject conditional termination edges.

        Steps performed:
        1. Replace each non-__start__ node's callable with a trust-evaluating wrapper.
        2. For each simple outgoing edge, inject a conditional edge that routes to
           END when should_terminate() is True, preserving the normal next node
           otherwise.
        3. Delegate to the underlying StateGraph.compile(**kwargs).

        Args:
            **kwargs: Forwarded verbatim to StateGraph.compile().

        Returns:
            A compiled LangGraph runnable ready for invocation.
        """
        self._wrap_nodes()
        self._inject_termination_edges()
        graph: Any = self._graph
        return graph.compile(**kwargs)
