# Phase 2: LangGraph Adapter - Research

**Researched:** 2026-02-18
**Domain:** LangGraph StateGraph wrapping, circuit-breaker integration, optional dependency patterns
**Confidence:** HIGH (core patterns), MEDIUM (version compatibility nuance)

---

## Summary

LangGraph 1.0.x (current as of Feb 2026, requires Python >=3.10) is **incompatible** with this project's Python 3.9+ requirement. The last Python 3.9-compatible series is **LangGraph 0.2.x** (latest: 0.2.67, released Jan 2025). The adapter must be written defensively: its `[[tool.mypy.overrides]]` stanza must silence missing-import errors for `langgraph`, and the runtime guard must use `try/except ImportError`. The public API shape does not differ substantially between 0.2.x and 1.0.x for the patterns we need (add_node, add_conditional_edges, END).

The correct implementation strategy for `TrustAwareGraph` is **node-function wrapping at construction time**: iterate the user's `StateGraph.nodes` dict before compiling, replace each node's callable with a thin closure that calls the original and then feeds the output through `OutcomeClassifier` + `TrustManager`. After wrapping, add a supervisor node plus conditional edges from every original node to either the next node or the circuit-break terminus. This approach requires **zero changes** to user graph code because the user hands `TrustAwareGraph` their uncompiled `StateGraph` builder, and `TrustAwareGraph.compile()` does the surgery before calling `builder.compile()`.

**Primary recommendation:** Wrap at the `StateGraph` level (before compile), not at the `CompiledGraph` level, because node callables are directly accessible in `StateGraph.nodes` before compilation. Use `functools.wraps` to preserve introspection. Never subclass `CompiledGraph` — its internals are not part of the public API.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| LANG-01 | Developer can wrap any LangGraph StateGraph with TrustAwareGraph — zero changes to existing graph code | Node-function wrapping pattern: iterate `StateGraph.nodes`, replace callables in-place before `compile()`. User passes their existing `StateGraph` builder and gets back a compiled graph. |
| LANG-02 | TrustAwareGraph automatically classifies node outcomes (success/failure/uncertain) from node outputs | `OutcomeClassifier` inspects returned state dict: empty/None values → FAILURE, error-key presence → FAILURE, exact-repeat of prior state → PARTIAL, otherwise SUCCESS. |
| LANG-03 | TrustAwareGraph routes to recovery path when trust degrades below threshold | `add_conditional_edges` from each wrapped node to either the normal next node or `END` (circuit-break). Router function calls `trust_manager.should_terminate()`. |
| LANG-04 | Developer can register callbacks for on_trust_change, on_circuit_break, on_recovery events | `List[Callable]` registry per event type. Callbacks invoked synchronously after trust state mutation. Pattern is a simple observer list — no external library needed. |
</phase_requirements>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| langgraph | >=0.2.0,<1.0.0 (Python 3.9 bound) | StateGraph API, END sentinel, compiled graph execution | Only stable Python 3.9-compatible major series |
| fulcrum_trust (Phase 1) | internal | TrustManager, TrustOutcome, TrustState | Already implemented, this phase consumes it |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| typing_extensions | already in langgraph deps | Annotated, Protocol, TypedDict on 3.9 | When typing backports needed |
| functools | stdlib | `functools.wraps` for closure introspection | Always, when wrapping callables |
| pytest | >=7.0 (already in dev deps) | Test the adapter | Always |
| unittest.mock | stdlib | Mock LangGraph node callables in tests | Always — avoids real LLM dependency |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| langgraph 0.2.x | langgraph 1.0.x | 1.0.x requires Python 3.10+; breaks project's 3.9 support. Pin to <1.0 in optional dep spec. |
| Node-function wrapping | Subclassing CompiledGraph | CompiledGraph internals are not public API. Subclassing is fragile across versions. |
| Node-function wrapping | Post-processing via stream() | stream() approach can't inject routing before next node fires — misses the circuit-break window. |
| Simple callback list | asyncio events / queue | Overkill. Graphs are synchronous here; list of callables is correct and testable. |

**Installation (optional dep group to add to pyproject.toml):**
```bash
# Add to [project.optional-dependencies] in pyproject.toml:
# langgraph = ["langgraph>=0.2.0,<1.0.0"]

pip install "fulcrum-trust[langgraph]"
# or for dev:
pip install "langgraph>=0.2.0,<1.0.0"
```

---

## Architecture Patterns

### Recommended Project Structure
```
fulcrum_trust/adapters/
├── __init__.py           # exports TrustAwareGraph (conditional on langgraph)
└── langgraph.py          # TrustAwareGraph, OutcomeClassifier
tests/
└── test_langgraph_adapter.py  # mirrors adapter structure per CLAUDE.md convention
```

### Pattern 1: Optional Import Guard

The module-level guard that must appear at the top of `fulcrum_trust/adapters/langgraph.py`:

```python
# Source: https://adamj.eu/tech/2021/12/29/python-type-hints-optional-imports/
# and mypy docs: https://mypy.readthedocs.io/en/stable/config_file.html
from __future__ import annotations

from typing import TYPE_CHECKING

try:
    from langgraph.graph import StateGraph, END  # type: ignore[import]
    from langgraph.graph.state import CompiledStateGraph  # type: ignore[import]
    _LANGGRAPH_AVAILABLE = True
except ImportError:
    _LANGGRAPH_AVAILABLE = False

if TYPE_CHECKING:
    # Only imported for type-checker; never executed at runtime when missing
    from langgraph.graph import StateGraph, END
    from langgraph.graph.state import CompiledStateGraph
```

The `type: ignore[import]` comment suppresses mypy's missing-stubs error at the try-block level. The `if TYPE_CHECKING` block gives mypy full type information when langgraph IS installed. Additionally add to `pyproject.toml`:

```toml
[[tool.mypy.overrides]]
module = "langgraph.*"
ignore_missing_imports = true
```

**When to use:** Always, at the top of the langgraph adapter module. `_LANGGRAPH_AVAILABLE` is the runtime guard to raise a clean `ImportError` with a helpful message inside `TrustAwareGraph.__init__`.

### Pattern 2: Node-Function Wrapping (Core of LANG-01)

The key insight: before calling `builder.compile()`, `StateGraph.nodes` is a plain `dict[str, StateNodeSpec]`. Each `StateNodeSpec` holds the callable in its `.runnable` attribute (which is a `RunnableLambda` wrapping the original function). The safe, version-stable approach is to **replace the node's action at the dict level** by re-calling `add_node` with the wrapped callable. Since adding a node with the same name raises an error, remove + re-add using `builder.nodes.pop(name)` and `builder.add_node(name, wrapped_fn)`.

Alternatively (simpler and more stable): instead of mutating the builder, **create a new `StateGraph` with the same state schema**, re-register all nodes with wrapped callables, re-register all edges, then compile. This avoids relying on `StateNodeSpec` internals.

```python
# Source: LangGraph graph API docs https://docs.langchain.com/oss/python/langgraph/graph-api
import functools
from typing import Any, Callable

def _wrap_node(
    node_fn: Callable[[Any], Any],
    node_name: str,
    agent_a: str,
    agent_b: str,
    trust_manager: TrustManager,
    classifier: OutcomeClassifier,
    callbacks: CallbackRegistry,
) -> Callable[[Any], Any]:
    @functools.wraps(node_fn)
    def wrapped(state: Any) -> Any:
        result = node_fn(state)
        outcome = classifier.classify(state, result)
        trust_state = trust_manager.evaluate(agent_a, agent_b, outcome)
        callbacks.fire_trust_change(trust_state)
        if trust_manager.should_terminate(agent_a, agent_b):
            callbacks.fire_circuit_break(trust_state)
        return result
    return wrapped
```

**When to use:** Always. This is the canonical wrapping approach: no subclassing, no patching of internals, no changes to user's builder.

### Pattern 3: Conditional Edge for Circuit-Break Routing (LANG-03)

After registering all wrapped nodes, add a conditional edge from each node that checks the trust state:

```python
# Source: LangGraph graph API docs https://docs.langchain.com/oss/python/langgraph/graph-api
from langgraph.graph import END

def make_trust_router(
    agent_a: str,
    agent_b: str,
    trust_manager: TrustManager,
    normal_next: str,
) -> Callable[[Any], str]:
    def router(state: Any) -> str:
        if trust_manager.should_terminate(agent_a, agent_b):
            return END  # type: ignore[return-value]
        return normal_next
    return router

# Usage during graph construction:
new_builder.add_conditional_edges(
    node_name,
    make_trust_router(agent_a, agent_b, trust_manager, next_node),
    {END: END, next_node: next_node},
)
```

**Limitation:** This pattern works cleanly for linear or simple branching graphs. For graphs with existing conditional edges, `TrustAwareGraph` must replicate the original routing logic AND add the trust check. Implementation strategy: for each original edge, if it was a `conditional_edge`, wrap the original path function to prepend the trust check; if it was a direct `edge`, replace with a conditional that checks trust first.

**When to use:** After all nodes are registered. Must handle both regular edges and conditional edges from the original graph.

### Pattern 4: Callback Registry (LANG-04)

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, List
from fulcrum_trust.types import TrustState

# Callback type aliases
TrustChangeCallback = Callable[[TrustState], None]
CircuitBreakCallback = Callable[[TrustState], None]
RecoveryCallback = Callable[[TrustState], None]

@dataclass
class CallbackRegistry:
    """Holds lists of callbacks for each trust event type."""
    on_trust_change: List[TrustChangeCallback] = field(default_factory=list)
    on_circuit_break: List[CircuitBreakCallback] = field(default_factory=list)
    on_recovery: List[RecoveryCallback] = field(default_factory=list)

    def fire_trust_change(self, state: TrustState) -> None:
        for cb in self.on_trust_change:
            cb(state)

    def fire_circuit_break(self, state: TrustState) -> None:
        for cb in self.on_circuit_break:
            cb(state)

    def fire_recovery(self, state: TrustState) -> None:
        for cb in self.on_recovery:
            cb(state)
```

**When to use:** Instantiated inside `TrustAwareGraph.__init__`. Expose `on_trust_change`, `on_circuit_break`, `on_recovery` as public registration methods that append to the lists.

### Pattern 5: OutcomeClassifier (LANG-02)

Classifies node return values (always `dict` in LangGraph) into `TrustOutcome`:

```python
from fulcrum_trust.types import TrustOutcome
from typing import Any

class OutcomeClassifier:
    """Heuristic classifier of LangGraph node outputs into TrustOutcome."""

    # Keys whose presence in the output dict signals failure
    ERROR_KEYS: frozenset[str] = frozenset({"error", "exception", "traceback"})

    def classify(self, prior_state: Any, node_output: Any) -> TrustOutcome:
        # None output -> FAILURE
        if node_output is None:
            return TrustOutcome.FAILURE

        # Non-dict output from a node is unexpected -> FAILURE
        if not isinstance(node_output, dict):
            return TrustOutcome.FAILURE

        # Empty dict -> FAILURE (node produced no update)
        if not node_output:
            return TrustOutcome.FAILURE

        # Error keys present -> FAILURE
        if any(k in node_output for k in self.ERROR_KEYS):
            return TrustOutcome.FAILURE

        # Repetitive: output is identical to relevant prior state keys -> PARTIAL
        if isinstance(prior_state, dict):
            overlapping_keys = set(node_output) & set(prior_state)
            if overlapping_keys:
                if all(node_output[k] == prior_state[k] for k in overlapping_keys):
                    return TrustOutcome.PARTIAL

        return TrustOutcome.SUCCESS
```

**When to use:** Instantiated once in `TrustAwareGraph`, shared across all wrapped nodes.

### Anti-Patterns to Avoid

- **Subclassing CompiledGraph or CompiledStateGraph:** These classes have private internal structure that changes between LangGraph versions. `CompiledGraph` is not intended to be subclassed per the docs.
- **Patching compiled graph post-compile:** After `builder.compile()`, nodes are sealed into Pregel execution tasks. There is no clean hook to intercept a compiled graph's individual node invocations.
- **Using `stream()` for interception:** Streaming mode yields state snapshots between steps but does not allow aborting execution mid-stream without external thread cancellation. Not suitable for synchronous circuit-breaking.
- **Wrapping `invoke()` only:** Wrapping the outer `invoke()` call only gives you the final state, not per-node outcomes, so you cannot do per-node trust scoring.
- **Storing trust state in LangGraph state dict:** This pollutes the user's state schema and violates LANG-01 (zero changes to existing graph code). Use `TrustManager` (external store) instead.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Callable introspection | Custom `__name__` extraction | `functools.wraps` | Preserves `__name__`, `__doc__`, `__module__`, `__qualname__` — essential for LangGraph node name inference |
| Beta distribution trust math | Custom Bayesian update | `TrustManager` (Phase 1) | Already implemented and tested to 95%+ coverage |
| Graph compilation | Custom execution engine | `StateGraph.compile()` → `CompiledStateGraph` | LangGraph handles parallelism, checkpointing, async execution |
| Error key detection | Complex NLP classifier | Simple `frozenset` key check + None/empty checks | LLM error outputs in LangGraph nearly always surface as `{"error": "..."}` dict keys |

**Key insight:** Trust scoring is already done. This phase is purely about plumbing: intercept outputs → classify → score → route. Keep the adapter thin.

---

## Common Pitfalls

### Pitfall 1: LangGraph 1.0 / Python 3.10 Incompatibility
**What goes wrong:** Installing `langgraph` without a version pin pulls in 1.0.x, which fails on Python 3.9 with a `SyntaxError` or `ImportError` because 1.0.x uses `match` statements and `ParamSpec` without backports.
**Why it happens:** LangGraph 1.0.0 dropped Python 3.9 support (October 2025, after Python 3.9 EOL).
**How to avoid:** Pin optional dep as `langgraph>=0.2.0,<1.0.0` in `pyproject.toml`. Also pin in dev dependencies for tests.
**Warning signs:** `pip install langgraph` in CI on Python 3.9 prints no warning but `import langgraph` silently fails or syntax-errors later.

### Pitfall 2: Accessing StateNodeSpec Internals
**What goes wrong:** Code accesses `builder.nodes[name].runnable` to extract the original callable. This attribute name changed between LangGraph 0.1 and 0.2 and may change again.
**Why it happens:** `StateNodeSpec` is an internal dataclass, not part of the public API.
**How to avoid:** Reconstruct the new builder by re-registering nodes. Accept the original callable from the user separately (e.g., a `node_map` dict), or iterate `builder.nodes` only to get node names and re-use user-provided callables.
**Warning signs:** Tests pass on 0.2.x but fail on 0.2.50 when the internal attribute was renamed.

### Pitfall 3: Missing `END` Import Path Changes
**What goes wrong:** `from langgraph.graph import END` worked in 0.1.x but moved in 0.2.x; or the sentinel changes from a string to a special object.
**Why it happens:** LangGraph reorganized exports between minor versions.
**How to avoid:** Always import `END` and `START` from `langgraph.graph` (the stable public module). Test `type(END)` in your import smoke test.
**Warning signs:** `ImportError: cannot import name 'END' from 'langgraph.graph'`.

### Pitfall 4: Conditional Edge Path Map Completeness
**What goes wrong:** `add_conditional_edges` router returns `END` but `END` is not in the `path_map` dict → LangGraph raises `ValueError` at compile time.
**Why it happens:** LangGraph 0.2.x validates that all possible return values from the router function appear as keys in `path_map`.
**How to avoid:** Always include `{END: END, ...normal_routes...}` as the `path_map` argument.
**Warning signs:** `ValueError: ... not in path_map` on graph compilation.

### Pitfall 5: Wrapping Async Node Functions
**What goes wrong:** Some LangGraph nodes are `async def`. A sync wrapper breaks async execution.
**Why it happens:** LangGraph supports both sync and async node callables. Wrapping an async node in a sync function drops `await`.
**How to avoid:** Detect `asyncio.iscoroutinefunction(node_fn)` and produce an `async def wrapped(state)` in that case.
**Warning signs:** `RuntimeWarning: coroutine was never awaited` in tests.

### Pitfall 6: Repetition Detection False Positives
**What goes wrong:** A valid node that intentionally returns unchanged state keys (e.g., a pass-through node) is classified as PARTIAL repeatedly, draining trust.
**Why it happens:** The naive repetition check compares all overlapping keys without semantic awareness.
**How to avoid:** Add a minimum-change threshold or limit repetition classification to high-cardinality values (strings > 20 chars, lists). Allow configuration via `OutcomeClassifier` constructor params.
**Warning signs:** Trust drops to PARTIAL immediately on a graph where some nodes are intentionally stateless.

---

## Code Examples

### Full TrustAwareGraph Skeleton
```python
# Source: LangGraph graph API docs + this codebase's Phase 1 types
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, List, Optional
import functools

from fulcrum_trust.manager import TrustManager
from fulcrum_trust.types import TrustOutcome, TrustState

try:
    from langgraph.graph import StateGraph, END  # type: ignore[import]
    _LANGGRAPH_AVAILABLE = True
except ImportError:
    _LANGGRAPH_AVAILABLE = False

if TYPE_CHECKING:
    from langgraph.graph import StateGraph, END


class TrustAwareGraph:
    """Wraps a LangGraph StateGraph with automatic trust evaluation at node boundaries.

    Args:
        graph: An uncompiled LangGraph StateGraph builder.
        trust_manager: TrustManager instance for trust scoring and circuit breaking.
        agent_a: Identifier for the caller/orchestrator agent.
        agent_b: Identifier for the callee/worker agent.
    """

    def __init__(
        self,
        graph: "StateGraph",
        trust_manager: TrustManager,
        agent_a: str = "orchestrator",
        agent_b: str = "worker",
    ) -> None:
        if not _LANGGRAPH_AVAILABLE:
            raise ImportError(
                "langgraph is required for TrustAwareGraph. "
                "Install it with: pip install 'fulcrum-trust[langgraph]'"
            )
        self._graph = graph
        self._trust_manager = trust_manager
        self._agent_a = agent_a
        self._agent_b = agent_b
        self._classifier = OutcomeClassifier()
        self._callbacks = CallbackRegistry()

    def on_trust_change(self, callback: Callable[[TrustState], None]) -> None:
        self._callbacks.on_trust_change.append(callback)

    def on_circuit_break(self, callback: Callable[[TrustState], None]) -> None:
        self._callbacks.on_circuit_break.append(callback)

    def on_recovery(self, callback: Callable[[TrustState], None]) -> None:
        self._callbacks.on_recovery.append(callback)

    def compile(self, **kwargs: Any) -> Any:
        """Wrap all nodes, inject trust routing, and compile the graph."""
        # ... wrapping logic here
        return self._graph.compile(**kwargs)
```

### Testing Without Real LLMs
```python
# Source: LangGraph testing docs https://docs.langchain.com/oss/python/langgraph/test
# and project test patterns (tests/test_manager.py)
import pytest
from typing import Any, Dict
from langgraph.graph import StateGraph, END
from typing_extensions import TypedDict

class SimpleState(TypedDict):
    value: str
    count: int

def make_simple_graph() -> StateGraph:
    """Build a minimal graph with two plain-function nodes — no LLM needed."""
    builder = StateGraph(SimpleState)

    def node_a(state: SimpleState) -> Dict[str, Any]:
        return {"count": state["count"] + 1}

    def node_b(state: SimpleState) -> Dict[str, Any]:
        return {"value": "done"}

    builder.add_node("node_a", node_a)
    builder.add_node("node_b", node_b)
    builder.add_edge("__start__", "node_a")
    builder.add_edge("node_a", "node_b")
    builder.add_edge("node_b", END)
    return builder

def test_trust_aware_graph_wraps_nodes():
    from fulcrum_trust import TrustManager
    from fulcrum_trust.adapters.langgraph import TrustAwareGraph

    tm = TrustManager()
    builder = make_simple_graph()
    wrapper = TrustAwareGraph(builder, tm, agent_a="a", agent_b="b")
    compiled = wrapper.compile()
    result = compiled.invoke({"value": "start", "count": 0})
    assert result["count"] == 1
    assert result["value"] == "done"

def test_circuit_break_fires_callback():
    from fulcrum_trust import TrustManager, TrustConfig, TrustOutcome
    from fulcrum_trust.adapters.langgraph import TrustAwareGraph

    fired: list = []
    cfg = TrustConfig(threshold=0.9)  # Very high threshold to trigger easily
    tm = TrustManager(config=cfg)
    # Pre-seed failures to ensure trust is below threshold
    tm.evaluate("a", "b", TrustOutcome.FAILURE)
    tm.evaluate("a", "b", TrustOutcome.FAILURE)
    tm.evaluate("a", "b", TrustOutcome.FAILURE)

    builder = make_simple_graph()
    wrapper = TrustAwareGraph(builder, tm, agent_a="a", agent_b="b")
    wrapper.on_circuit_break(lambda state: fired.append(state))
    compiled = wrapper.compile()
    # Invoke — trust is already below threshold, circuit-break callback should fire
    compiled.invoke({"value": "start", "count": 0})
    assert len(fired) > 0
```

### Detecting Async Nodes
```python
import asyncio
import functools
from typing import Any, Callable

def wrap_node_fn(
    node_fn: Callable[[Any], Any],
    *args: Any,
    **kwargs: Any,
) -> Callable[[Any], Any]:
    """Detect async node functions and return the correct wrapper type."""
    if asyncio.iscoroutinefunction(node_fn):
        @functools.wraps(node_fn)
        async def async_wrapped(state: Any) -> Any:
            result = await node_fn(state)
            # ... trust evaluation ...
            return result
        return async_wrapped
    else:
        @functools.wraps(node_fn)
        def sync_wrapped(state: Any) -> Any:
            result = node_fn(state)
            # ... trust evaluation ...
            return result
        return sync_wrapped
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| LangGraph 0.1.x MessageGraph | StateGraph with messages key | mid-2024 | MessageGraph deprecated; use StateGraph |
| `from langgraph.prebuilt import ToolNode` (separate package) | langgraph-prebuilt | LangGraph 1.0.0 | langgraph-prebuilt is now a separate dependency in 1.0.x |
| `add_node(name, fn)` accepting only positional args | Keyword-only `defer`, `metadata`, `cache_policy` args | 0.2.x | Add nodes with positional args only for 3.9 compat |
| Python 3.9 support | Dropped in 1.0.0 | 1.0.0 (Jan 2026) | Pin `langgraph<1.0.0` in optional dep |

**Deprecated/outdated:**
- `MessageGraph`: Replaced by `StateGraph` with a `messages` key of `Annotated[list, add_messages]`. Do not use in new code.
- `create_react_agent` from `langgraph.prebuilt`: In 1.0.x moved to `langchain.agents`. Irrelevant to this adapter but do not import.

---

## Open Questions

1. **StateGraph.nodes internal access stability**
   - What we know: `StateGraph.nodes` is a public dict attribute in 0.2.x; `StateNodeSpec` is internal.
   - What's unclear: Whether accessing `StateGraph.nodes` keys (node names only, not internals) is stable across 0.2.x patch versions.
   - Recommendation: Use `list(builder.nodes.keys())` only to enumerate node names. Require the user to pass a separate `node_callables: dict[str, Callable]` mapping, or reconstruct nodes from the builder's declared structure. Avoids all `StateNodeSpec` internals.

2. **Edge introspection API**
   - What we know: `StateGraph` has `edges` (set of tuples) and `branches` (dict of conditional edges) attributes, but these are internal.
   - What's unclear: Whether we can reliably reconstruct all edges from a user's `StateGraph` to build the wrapped version.
   - Recommendation: Instead of introspecting edges, have `TrustAwareGraph` accept the user's `StateGraph` **and** compile it directly (injecting trust as conditional edges on top). Use `interrupt_after` on all nodes as a hook point if edge reconstruction proves unreliable. Alternatively, simplify Phase 2 scope: inject a single `trust_router` node that runs after every step, rather than per-node conditional edges.

3. **Recovery callback trigger**
   - What we know: `TrustManager.reset()` exists (from Phase 1) and can restore trust. `on_recovery` should fire when trust crosses back above threshold.
   - What's unclear: "Recovery" in a circuit breaker usually means the circuit closes again. In a terminated LangGraph, the graph has already stopped — recovery would only apply if the user calls `TrustManager.reset()` and re-invokes the wrapped graph.
   - Recommendation: Fire `on_recovery` when `should_terminate()` was True on the previous node evaluation but is now False after a `reset()`. Simplest implementation: store `_was_terminated: bool` on the wrapper and check on each node evaluation.

---

## Sources

### Primary (HIGH confidence)
- Official LangGraph graph API docs: https://docs.langchain.com/oss/python/langgraph/graph-api — StateGraph constructor, add_node, add_conditional_edges, compile signatures with examples
- LangGraph reference API: https://reference.langchain.com/python/langgraph/graphs/ — add_node/add_edge/compile full signatures
- LangGraph pyproject.toml (main branch, fetched directly): `requires-python = ">=3.10"`, confirmed 1.0.8 as current release
- PyPI langgraph 0.2.67: Python >=3.9.0,<4.0 — confirmed last 3.9-compatible release
- LangGraph testing docs: https://docs.langchain.com/oss/python/langgraph/test — `compiled_graph.nodes["name"].invoke()` pattern, no-LLM testing
- Mypy optional import docs: https://adamj.eu/tech/2021/12/29/python-type-hints-optional-imports/ — boolean flag pattern

### Secondary (MEDIUM confidence)
- GitHub issue #1366 langchain-ai/langgraph: confirms 3.9 was minimum for 0.2.x, root pyproject.toml is monorepo-only
- LangGraph v1 migration guide: https://docs.langchain.com/oss/python/migrate/langgraph-v1 — confirms Python 3.10+ for 1.0
- pycircuitbreaker PyPI: callback pattern (on_open/on_close) confirms callback-as-constructor-param is ecosystem convention
- Mypy config docs: https://mypy.readthedocs.io/en/stable/config_file.html — `[[tool.mypy.overrides]]` with `ignore_missing_imports`

### Tertiary (LOW confidence — for validation)
- LangGraph StateNodeSpec internal structure: fetched from GitHub main branch. Attribute names (`runnable`, `ends`, `defer`) may drift; flagged as internal API, do not rely on in implementation.
- Async node handling pattern: inferred from `asyncio.iscoroutinefunction` docs + LangGraph's known async support. Not directly verified with a LangGraph async node test.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — version constraints verified directly from pyproject.toml and PyPI
- Architecture: HIGH — node-function wrapping pattern is standard Python; StateGraph API verified from official docs
- Pitfalls: MEDIUM — most verified from official docs; async pitfall inferred from Python stdlib
- Version compatibility: HIGH — Python 3.9/3.10 boundary confirmed from multiple official sources

**Research date:** 2026-02-18
**Valid until:** 2026-04-18 (LangGraph 0.2.x is in maintenance mode; unlikely to change. If project upgrades Python requirement to 3.10+, re-evaluate using 1.0.x.)
