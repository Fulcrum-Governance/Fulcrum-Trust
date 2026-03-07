# API Reference

This document covers all public classes and methods in `fulcrum-trust`. All classes are importable directly from `fulcrum_trust`.

```python
from fulcrum_trust import TrustManager, TrustOutcome, TrustState, TrustConfig, TrustCircuitOpen, MemoryStore, FileStore
from fulcrum_trust.adapters.langgraph import TrustAwareGraph
```

---

## TrustManager

The primary interface. Orchestrates trust evaluation, storage, and decay.

::: fulcrum_trust.manager.TrustManager
    options:
      docstring_style: google
      show_root_heading: true
      show_source: false

**Constructor:**

```python
TrustManager(store=None, config=None, *, async_flush=False)
```

- `store` — A `TrustStore` instance. Defaults to `MemoryStore()`.
- `config` — A `TrustConfig` instance. Defaults to `TrustConfig()`.
- `async_flush` — When `True`, routes store writes through a `BackgroundFlusher` for non-blocking persistence. Default `False`.

**Key methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `evaluate` | `(agent_a, agent_b, outcome, *, raise_on_break=False) -> TrustState` | Record an interaction result; applies decay first, then Bayesian update. Optionally raises `TrustCircuitOpen` when trust drops below threshold. |
| `get_trust_score` | `(agent_a, agent_b) -> float` | Current trust score (0.0–1.0, starts at 0.5 for unknown pairs) |
| `should_terminate` | `(agent_a, agent_b) -> bool` | True if trust score is below `config.threshold` |
| `get_state` | `(agent_a, agent_b) -> TrustState \| None` | Raw TrustState with alpha/beta/timestamp, or None if not yet evaluated |
| `reset` | `(agent_a, agent_b) -> None` | Remove trust history; pair reverts to uninformative prior (0.5) |

**Agent pair ordering:** `("orchestrator", "worker")` and `("worker", "orchestrator")` refer to the same pair. Order does not matter.

**Example:**

```python
from fulcrum_trust import TrustManager, TrustOutcome

tm = TrustManager()

tm.evaluate("orchestrator", "worker", TrustOutcome.SUCCESS)
tm.evaluate("orchestrator", "worker", TrustOutcome.FAILURE)

print(tm.get_trust_score("orchestrator", "worker"))  # 0.6
print(tm.should_terminate("orchestrator", "worker"))  # False
```

---

## TrustState

::: fulcrum_trust.types.TrustState
    options:
      docstring_style: google
      show_root_heading: true
      show_source: false

Dataclass holding the Beta distribution parameters for an agent pair.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `pair_id` | `str` | Canonical identifier for the agent pair (sorted join) |
| `agent_a` | `str` | First agent identifier |
| `agent_b` | `str` | Second agent identifier |
| `alpha` | `float` | Positive evidence accumulator (default 1.0 uninformative prior) |
| `beta_val` | `float` | Negative evidence accumulator (default 1.0 uninformative prior) |
| `last_updated` | `float` | Unix timestamp of last state mutation |
| `interaction_count` | `int` | Total number of recorded interactions |
| `circuit_state` | `str` | Circuit breaker state: `"CLOSED"`, `"OPEN"`, or `"HALF_OPEN"`. Default `"CLOSED"`. |

**Property:**

- `trust_score -> float` — Beta distribution mean: `alpha / (alpha + beta_val)`.

**Example:**

```python
state = tm.get_state("orchestrator", "worker")
if state:
    print(f"alpha={state.alpha}, beta_val={state.beta_val}")
    print(f"trust_score={state.trust_score:.3f}")
    print(f"interactions={state.interaction_count}")
```

---

## TrustOutcome

::: fulcrum_trust.types.TrustOutcome
    options:
      docstring_style: google
      show_root_heading: true
      show_source: false

Enum representing the result of an agent-to-agent interaction.

**Values:**

| Value | String | Effect |
|-------|--------|--------|
| `TrustOutcome.SUCCESS` | `"success"` | Increments `alpha` by `config.success_weight` (default 1.0) |
| `TrustOutcome.FAILURE` | `"failure"` | Increments `beta_val` by `config.failure_weight` (default 1.0) |
| `TrustOutcome.PARTIAL` | `"partial"` | Increments both `alpha` by `partial_alpha_weight` and `beta_val` by `partial_beta_weight` |

**Example:**

```python
from fulcrum_trust import TrustOutcome

# Mark an interaction as partially successful
tm.evaluate("agent-a", "agent-b", TrustOutcome.PARTIAL)
```

---

## TrustConfig

::: fulcrum_trust.types.TrustConfig
    options:
      docstring_style: google
      show_root_heading: true
      show_source: false

Configuration dataclass passed to `TrustManager`. All fields have defaults.

**Fields:**

| Field | Default | Description |
|-------|---------|-------------|
| `threshold` | `0.3` | Trust score below which `should_terminate()` returns `True` |
| `half_life_seconds` | `86400.0` | Time (seconds) for trust to decay halfway toward 0.5 (default: 24h) |
| `alpha_prior` | `1.0` | Initial alpha for new pairs (uninformative prior) |
| `beta_prior` | `1.0` | Initial beta for new pairs (uninformative prior) |
| `success_weight` | `1.0` | Alpha increment per `SUCCESS` outcome |
| `failure_weight` | `1.0` | Beta increment per `FAILURE` outcome |
| `partial_alpha_weight` | `0.5` | Alpha increment per `PARTIAL` outcome |
| `partial_beta_weight` | `0.5` | Beta increment per `PARTIAL` outcome |

**Validation:** `threshold` must be in `(0, 1)`. `half_life_seconds` must be positive.

**Example:**

```python
from fulcrum_trust import TrustManager, TrustConfig

tm = TrustManager(
    config=TrustConfig(
        threshold=0.4,               # Break earlier
        half_life_seconds=3600,      # 1-hour decay
        partial_beta_weight=0.8,     # PARTIAL counts heavily against trust
    )
)
```

---

## TrustCircuitOpen

Exception raised when `raise_on_break=True` and trust drops below the configured threshold after an evaluation.

**Constructor:**

```python
TrustCircuitOpen(pair_id: str, trust_score: float, threshold: float)
```

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `pair_id` | `str` | Canonical pair identifier |
| `trust_score` | `float` | Trust score at time of circuit break |
| `threshold` | `float` | Configured threshold that was violated |

**Example:**

```python
from fulcrum_trust import TrustManager, TrustOutcome, TrustCircuitOpen

tm = TrustManager()
tm.evaluate("a", "b", TrustOutcome.FAILURE)

try:
    tm.evaluate("a", "b", TrustOutcome.FAILURE, raise_on_break=True)
except TrustCircuitOpen as exc:
    print(f"Circuit open: {exc.pair_id} at {exc.trust_score:.3f}")
```

---

## Stores

### MemoryStore

::: fulcrum_trust.stores.memory.MemoryStore
    options:
      docstring_style: google
      show_root_heading: true
      show_source: false

In-process dict-backed store. Default when creating `TrustManager()`. Does not persist across process restarts.

**Usage:** Used automatically as the default store. No configuration needed.

```python
from fulcrum_trust import TrustManager

tm = TrustManager()  # Uses MemoryStore by default
```

**Methods:** `get(pair_id)`, `put(pair_id, state)`, `delete(pair_id)`.

### FileStore

::: fulcrum_trust.stores.file.FileStore
    options:
      docstring_style: google
      show_root_heading: true
      show_source: false

JSON file-backed store. Persists trust state across process restarts. Thread-safe via file locking.

**Constructor:** `FileStore(path)` — path to the JSON file (created if it does not exist).

```python
from fulcrum_trust import TrustManager
from fulcrum_trust.stores.file import FileStore

tm = TrustManager(store=FileStore("trust_state.json"))
```

**Methods:** `get(pair_id)`, `put(pair_id, state)`, `delete(pair_id)`.

### Custom Stores

Implement the `TrustStore` Protocol from `fulcrum_trust.stores.base`:

```python
from fulcrum_trust.stores.base import TrustStore
from fulcrum_trust.types import TrustState

class RedisStore:
    def get(self, pair_id: str) -> TrustState | None: ...
    def put(self, pair_id: str, state: TrustState) -> None: ...
    def delete(self, pair_id: str) -> None: ...

tm = TrustManager(store=RedisStore())
```

---

## BackgroundFlusher

Thread-safe background flusher for trust state events. Prevents synchronous store I/O from blocking the agent's execution loop.

**Constructor:**

```python
from fulcrum_trust.flusher import BackgroundFlusher

flusher = BackgroundFlusher(store, flush_interval=5.0, max_batch=100)
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `store` | (required) | TrustStore to flush events into |
| `flush_interval` | `5.0` | Seconds between automatic flushes |
| `max_batch` | `100` | Maximum events per flush cycle |

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `enqueue` | `(state: TrustState) -> None` | Add event to flush queue (non-blocking) |
| `flush` | `() -> None` | Drain queue and persist all pending events immediately |
| `shutdown` | `() -> None` | Flush remaining events and stop background thread |

**Usage with TrustManager:**

```python
from fulcrum_trust import TrustManager, TrustOutcome
from fulcrum_trust.stores.file import FileStore

# Opt-in: non-blocking persistence
tm = TrustManager(store=FileStore("trust.json"), async_flush=True)
tm.evaluate("orchestrator", "worker", TrustOutcome.SUCCESS)  # non-blocking write
```

---

## Context Isolation

ContextVar-based isolation for concurrent trust evaluations. Ensures that concurrent asyncio tasks or threads maintain independent evaluation context.

```python
from fulcrum_trust.context import get_current_context, set_trust_context, reset_trust_context

token = set_trust_context("agent_a|agent_b")
try:
    ctx = get_current_context()
    print(ctx.pair_id)  # "agent_a|agent_b"
finally:
    reset_trust_context(token)
```

This is used internally by `TrustManager.evaluate()` — you typically don't need to call these directly unless building custom adapters.

---

## LangGraph Adapter

### TrustAwareGraph

::: fulcrum_trust.adapters.langgraph.TrustAwareGraph
    options:
      docstring_style: google
      show_root_heading: true
      show_source: false

Wraps a compiled LangGraph `StateGraph` with automatic trust evaluation at node boundaries. Zero changes to existing graph code.

**Constructor:** `TrustAwareGraph(graph, trust_manager, outcome_classifier=None, callbacks=None)`

**Usage:**

```python
from langgraph.graph import StateGraph
from fulcrum_trust import TrustManager
from fulcrum_trust.adapters.langgraph import TrustAwareGraph

# Your existing graph (unchanged)
builder = StateGraph(MyState)
builder.add_node("orchestrator", orchestrator_fn)
builder.add_node("worker", worker_fn)
builder.add_edge("orchestrator", "worker")
graph = builder.compile()

# Wrap with trust
trust = TrustManager()
trusted_graph = TrustAwareGraph(graph, trust)

# Use exactly like the original graph
result = trusted_graph.invoke(initial_state)
```

The adapter intercepts node transitions, records outcomes, and injects termination edges when trust drops below threshold. No changes to your graph's nodes or edges are required.
