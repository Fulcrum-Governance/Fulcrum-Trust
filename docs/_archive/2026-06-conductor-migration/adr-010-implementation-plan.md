# ADR-010 Implementation Plan: Engineering Pattern Adoption

**Source ADR:** `docs/ADR-010-engineering-intel-adoption.md`
**Repo:** `fulcrum-trust` (`~/ConceptDev/Projects/fulcrum-trust`)
**Scope:** D1 patterns only (P-01, P-02, P-03) + types-level P-06 foundation
**Target:** Ship before March 17, 2026
**D2 patterns:** P-06 store persistence, P-08, P-05 in fulcrum-io — separate plan, separate sprint

---

## Current Codebase State (Verified March 6, 2026)

```
fulcrum_trust/
  __init__.py          # Exports: TrustManager, TrustOutcome, TrustState, TrustConfig,
                       #          MemoryStore, FileStore, FulcrumStore
  types.py             # TrustState, TrustConfig, TrustOutcome — NO circuit_state yet
  manager.py           # TrustManager — synchronous store.put() on every evaluate()
  evaluator.py         # TrustEvaluator, make_pair_id
  decay.py             # apply_decay()
  stores/
    base.py            # TrustStore protocol: get/put/delete/all_pairs
    memory.py          # MemoryStore
    file.py            # FileStore
    fulcrum.py         # FulcrumStore
  adapters/
    __init__.py
    langgraph.py       # LangGraph adapter (existing)
tests/
  test_types.py
  test_manager.py
  test_evaluator.py
  test_decay.py
  test_stores.py
  test_fulcrum_store.py
  test_fulcrum_store_integration.py
  test_langgraph_adapter.py
docs/
  api-reference.md     # Exists — must be updated
  ADR-010-engineering-intel-adoption.md
```

**What does NOT exist yet (to be created):**
- `fulcrum_trust/context.py` — ContextVar isolation module
- `fulcrum_trust/flusher.py` — BackgroundFlusher
- `tests/test_context.py`
- `tests/test_flusher.py`

---

## Dependency Graph

```
P-02: TrustCircuitOpen + circuit_state field (types.py only)
  |
  +---> P-03: ContextVar isolation (context.py + manager.py)
  |         |
  |         +---> P-01: BackgroundFlusher (flusher.py + manager.py)
  |                   |
  |                   +---> Tests (test_context.py, test_flusher.py, update test_manager.py, test_types.py)
  |                             |
  |                             +---> Docs (api-reference.md, README, CHANGELOG)
```

P-03 and P-01 both modify `manager.py` — they MUST be sequential, not parallel.
P-03 must land before P-01 because the flusher wiring in `manager.py` sits alongside the context wiring.

---

## Wave 1 — Foundation

**Owner:** Single team (no parallelism — pure types additions)
**Duration:** ~0.5 day
**Gate:** All existing tests still pass. CI green before Wave 2 begins.

### Task 1.1 — P-02: Add `TrustCircuitOpen` exception

**File:** `fulcrum_trust/types.py`

Add after the existing `TrustOutcome` enum:

```python
class TrustCircuitOpen(Exception):
    """Raised when trust drops below threshold and raise_on_break=True.

    Attributes:
        pair_id: Canonical pair identifier (sorted agent IDs joined by '|').
        trust_score: Current trust score at time of circuit break.
        threshold: Configured threshold that was violated.
    """

    def __init__(self, pair_id: str, trust_score: float, threshold: float) -> None:
        self.pair_id = pair_id
        self.trust_score = trust_score
        self.threshold = threshold
        super().__init__(
            f"Trust circuit open for pair '{pair_id}': "
            f"score {trust_score:.3f} < threshold {threshold:.3f}"
        )
```

### Task 1.2 — P-06 types foundation: Add `circuit_state` to `TrustState`

**File:** `fulcrum_trust/types.py`

Add one field to the `TrustState` dataclass:

```python
circuit_state: str = "CLOSED"  # CircuitBreakerState: CLOSED | OPEN | HALF_OPEN
```

This is a pure additive change with a default — all existing code and serialized data remains valid. The store persistence logic for circuit state is D2 work (not in this plan).

### Task 1.3 — Update `__init__.py` exports

**File:** `fulcrum_trust/__init__.py`

Add `TrustCircuitOpen` to imports and `__all__`:

```python
from fulcrum_trust.types import TrustConfig, TrustCircuitOpen, TrustOutcome, TrustState

__all__ = [
    "TrustCircuitOpen",
    "TrustManager",
    ...
]
```

### Task 1.4 — Update `tests/test_types.py`

Add tests for `TrustCircuitOpen`:
- Instantiate with `pair_id`, `trust_score`, `threshold`
- Verify `str(exc)` contains pair_id, score, threshold
- Verify it is an `Exception` subclass
- Verify attributes are accessible

Add test for `TrustState.circuit_state`:
- Default value is `"CLOSED"`
- Field exists and is a string

**Wave 1 success gate:** `pytest tests/test_types.py -v` passes. No other tests broken.

---

## Wave 2a — ContextVar Isolation (P-03)

**Owner:** Single team
**Depends on:** Wave 1 committed and CI green
**Duration:** ~1 day
**Gate:** `tests/test_context.py` passes. `tests/test_manager.py` still passes.

### Task 2a.1 — Create `fulcrum_trust/context.py`

New file. Complete implementation:

```python
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Optional


@dataclass
class TrustEvaluationContext:
    """Metadata for the currently active trust evaluation.

    Stored in a ContextVar so concurrent asyncio tasks or threads
    each maintain independent context without cross-contamination.
    """
    pair_id: str


# Module-level ContextVar. Default is None (no active evaluation).
_trust_context: ContextVar[Optional[TrustEvaluationContext]] = ContextVar(
    "_trust_context", default=None
)


def get_current_context() -> Optional[TrustEvaluationContext]:
    """Return the active TrustEvaluationContext, or None if not set."""
    return _trust_context.get()


def set_trust_context(pair_id: str) -> object:
    """Set the active context and return a Token for restoration.

    Usage::

        token = set_trust_context("agent_a|agent_b")
        try:
            ...
        finally:
            reset_trust_context(token)
    """
    return _trust_context.set(TrustEvaluationContext(pair_id=pair_id))


def reset_trust_context(token: object) -> None:
    """Restore the context to its state before set_trust_context was called."""
    _trust_context.reset(token)  # type: ignore[arg-type]
```

### Task 2a.2 — Wire context into `fulcrum_trust/manager.py`

Modify `TrustManager.evaluate()` to set context around the evaluation:

```python
from fulcrum_trust.context import reset_trust_context, set_trust_context

def evaluate(
    self,
    agent_a: str,
    agent_b: str,
    outcome: TrustOutcome,
    *,
    raise_on_break: bool = False,
) -> TrustState:
    """Record outcome and return updated trust state.

    Args:
        agent_a: First agent identifier.
        agent_b: Second agent identifier. Order does not matter.
        outcome: Interaction result (SUCCESS, FAILURE, or PARTIAL).
        raise_on_break: If True, raises TrustCircuitOpen when trust drops
            below the configured threshold after this evaluation.
            Default False (backward-compatible).

    Returns:
        Updated TrustState after decay and Bayesian update.

    Raises:
        TrustCircuitOpen: If raise_on_break=True and trust is below threshold.
    """
    from fulcrum_trust.types import TrustCircuitOpen  # avoid circular at module level

    pid = make_pair_id(agent_a, agent_b)
    token = set_trust_context(pid)
    try:
        state = self._store.get(pid)
        if state is None:
            state = self._evaluator.new_state(agent_a, agent_b)
        else:
            state = apply_decay(state, self._config.half_life_seconds)
        state = self._evaluator.update(state, outcome)
        self._store.put(pid, state)
    finally:
        reset_trust_context(token)

    if raise_on_break and self._evaluator.is_below_threshold(state):
        raise TrustCircuitOpen(
            pair_id=pid,
            trust_score=state.trust_score,
            threshold=self._config.threshold,
        )
    return state
```

**Important constraint:** `raise_on_break=False` is the default. Existing callers are completely unaffected.

### Task 2a.3 — Create `tests/test_context.py`

Test file covering:

1. `get_current_context()` returns `None` outside an evaluation
2. `set_trust_context()` sets the context; `get_current_context()` returns it
3. `reset_trust_context()` restores `None` after the call
4. **Concurrency test** — two concurrent `asyncio.gather()` calls evaluating different pairs do not cross-contaminate:

```python
import asyncio

async def test_context_isolation_concurrent():
    manager = TrustManager()
    results = []

    async def eval_pair(a, b, outcome):
        state = manager.evaluate(a, b, outcome)
        results.append((make_pair_id(a, b), state.trust_score))

    await asyncio.gather(
        eval_pair("agent_x", "agent_y", TrustOutcome.SUCCESS),
        eval_pair("agent_p", "agent_q", TrustOutcome.FAILURE),
    )

    scores = {r[0]: r[1] for r in results}
    assert scores["agent_x|agent_y"] > 0.5  # success
    assert scores["agent_p|agent_q"] < 0.5  # failure (after enough failures)
```

5. Test `raise_on_break=True` raises `TrustCircuitOpen` when trust is below threshold
6. Test `raise_on_break=False` (default) never raises even with low trust

**Wave 2a success gate:** `pytest tests/test_context.py tests/test_manager.py -v` passes. No regressions in full suite.

---

## Wave 2b — BackgroundFlusher (P-01)

**Owner:** Same team, after Wave 2a is committed
**Depends on:** Wave 2a committed and CI green
**Duration:** ~1.5 days
**Gate:** `tests/test_flusher.py` passes at 95%+ coverage. Full suite passes.

### Task 2b.1 — Create `fulcrum_trust/flusher.py`

Complete implementation:

```python
from __future__ import annotations

import atexit
import queue
import threading
import time
from typing import Optional

from fulcrum_trust.stores.base import TrustStore
from fulcrum_trust.types import TrustState


class BackgroundFlusher:
    """Thread-safe background flusher for trust state events.

    Accepts TrustState events via a non-blocking queue and persists them
    to the configured store in batches on a background thread. Prevents
    synchronous store I/O from blocking the agent's execution loop.

    Args:
        store: Persistence layer to flush events into.
        flush_interval: Seconds between automatic flushes. Default 5.0.
        max_batch: Maximum events per flush cycle. Default 100.

    Usage::

        flusher = BackgroundFlusher(store=FileStore("trust.json"))
        flusher.enqueue(state)  # non-blocking
        # flushes automatically; also flushes on process exit
    """

    def __init__(
        self,
        store: TrustStore,
        flush_interval: float = 5.0,
        max_batch: int = 100,
    ) -> None:
        self._store = store
        self._flush_interval = flush_interval
        self._max_batch = max_batch
        self._queue: queue.Queue[Optional[TrustState]] = queue.Queue()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="fulcrum-trust-flusher")
        self._thread.start()
        atexit.register(self.shutdown)

    def enqueue(self, state: TrustState) -> None:
        """Add a TrustState event to the flush queue (non-blocking).

        Args:
            state: Updated TrustState to persist asynchronously.
        """
        self._queue.put_nowait(state)

    def flush(self) -> None:
        """Drain the queue and persist all pending events immediately."""
        batch: list[TrustState] = []
        try:
            while True:
                item = self._queue.get_nowait()
                if item is None:
                    break
                batch.append(item)
        except queue.Empty:
            pass
        self._persist(batch)

    def shutdown(self) -> None:
        """Flush remaining events and stop the background thread gracefully."""
        self._stop_event.set()
        self._queue.put(None)  # sentinel to unblock the thread
        self._thread.join(timeout=10.0)
        self.flush()  # final drain of anything that arrived during join

    def _run(self) -> None:
        """Background thread: drain queue on interval or when batch is full."""
        while not self._stop_event.is_set():
            deadline = time.monotonic() + self._flush_interval
            batch: list[TrustState] = []
            while time.monotonic() < deadline and len(batch) < self._max_batch:
                try:
                    item = self._queue.get(timeout=0.1)
                    if item is None:
                        return  # shutdown sentinel
                    batch.append(item)
                except queue.Empty:
                    pass
            if batch:
                self._persist(batch)

    def _persist(self, batch: list[TrustState]) -> None:
        """Write a batch of TrustState objects to the store."""
        for state in batch:
            self._store.put(state.pair_id, state)
```

### Task 2b.2 — Wire flusher into `fulcrum_trust/manager.py`

Add `async_flush` parameter to `TrustManager.__init__()`:

```python
from fulcrum_trust.flusher import BackgroundFlusher

def __init__(
    self,
    store: TrustStore | None = None,
    config: TrustConfig | None = None,
    *,
    async_flush: bool = False,
) -> None:
    self._config = config if config is not None else TrustConfig()
    self._store: TrustStore = store if store is not None else MemoryStore()
    self._evaluator = TrustEvaluator(self._config)
    self._flusher: BackgroundFlusher | None = None
    if async_flush:
        self._flusher = BackgroundFlusher(self._store)
```

Modify the `evaluate()` store write to route through flusher when active:

```python
# In evaluate(), replace:
self._store.put(pid, state)

# With:
if self._flusher is not None:
    self._flusher.enqueue(state)
else:
    self._store.put(pid, state)
```

**Constraint:** `async_flush=False` is the default. All existing code is backward-compatible.

### Task 2b.3 — Create `tests/test_flusher.py`

Test file covering:

1. `BackgroundFlusher` instantiates and starts background thread
2. `enqueue()` is non-blocking
3. After `flush()`, all queued events are persisted to the store
4. After `shutdown()`, remaining events are persisted and thread stops
5. `max_batch` limit: enqueue 200 events, verify they flush in multiple cycles
6. `flush_interval` is respected (use a short interval in tests, e.g., 0.1s)
7. `atexit` registration: verify `shutdown` is registered (check `atexit._atexit` or mock)
8. Thread safety: multiple threads calling `enqueue()` concurrently — no data loss

**Integration test (also in `test_flusher.py`):**

```python
def test_integration_async_flush_with_file_store(tmp_path):
    """TrustManager with async_flush=True persists events via FileStore."""
    store = FileStore(str(tmp_path / "trust.json"))
    manager = TrustManager(store=store, async_flush=True)

    manager.evaluate("agent_a", "agent_b", TrustOutcome.SUCCESS)
    manager.evaluate("agent_a", "agent_b", TrustOutcome.SUCCESS)

    # Force flush
    manager._flusher.flush()

    # Read directly from store to verify persistence
    pair_id = make_pair_id("agent_a", "agent_b")
    state = store.get(pair_id)
    assert state is not None
    assert state.interaction_count == 2
```

**Update `tests/test_manager.py`:**
- Add test: `TrustManager(async_flush=True)` creates a flusher
- Add test: `TrustManager(async_flush=False)` (default) has `_flusher is None`
- Add test: `async_flush=True` routes writes through flusher, not direct store

**Wave 2b success gate:** `pytest tests/ -v --cov=fulcrum_trust --cov-report=term-missing` shows 95%+ on all new modules.

---

## Wave 3 — Documentation

**Owner:** Can start after Wave 2a commits (no file conflicts with Wave 2b)
**Parallel with:** Wave 2b — Documenter teammate begins once Wave 2a is green
**Duration:** ~0.5 day

> Wave 2a establishes the full public API surface (`TrustCircuitOpen`, `raise_on_break`,
> `context.py`). The flusher (`Wave 2b`) adds `BackgroundFlusher` and `async_flush` —
> document those as Wave 2b commits, or draft them from the spec in this plan.

### Task 3.1 — Update `docs/api-reference.md`

Add sections for:

**`TrustCircuitOpen` exception:**
```
TrustCircuitOpen(pair_id, trust_score, threshold)
  Raised when raise_on_break=True and trust drops below threshold.
  Attributes: pair_id (str), trust_score (float), threshold (float)
```

**`BackgroundFlusher` class:**
```
BackgroundFlusher(store, flush_interval=5.0, max_batch=100)
  enqueue(state: TrustState) -> None
  flush() -> None
  shutdown() -> None
```

**Updated `TrustManager.__init__` signature:**
```
TrustManager(store=None, config=None, *, async_flush=False)
```

**Updated `TrustManager.evaluate` signature:**
```
evaluate(agent_a, agent_b, outcome, *, raise_on_break=False) -> TrustState
```

**`TrustState.circuit_state` field:**
```
circuit_state: str = "CLOSED"
  Circuit breaker state. Values: "CLOSED" | "OPEN" | "HALF_OPEN".
  Populated by D2 store persistence (not yet active in D1).
```

### Task 3.2 — Update README architecture section

Add `flusher.py` and `context.py` to the module diagram. Brief description of each:
- `flusher.py` — Background telemetry batching (non-blocking store writes)
- `context.py` — ContextVar isolation for concurrent evaluations

### Task 3.3 — Update `CHANGELOG.md`

Add under next version (v0.2.0 or equivalent):

```
### Added
- `TrustCircuitOpen` exception: raised when `raise_on_break=True` and trust
  drops below threshold after an evaluation (P-02, ADR-010)
- `BackgroundFlusher`: thread-safe background batching for trust state events,
  preventing synchronous store I/O from blocking agent execution (P-01, ADR-010)
- `fulcrum_trust/context.py`: ContextVar-based execution isolation for concurrent
  evaluations — Graph A trust state cannot contaminate Graph B (P-03, ADR-010)
- `TrustManager(async_flush=True)`: opt-in async event persistence via BackgroundFlusher
- `TrustManager.evaluate(raise_on_break=True)`: opt-in exception on circuit break
- `TrustState.circuit_state` field (foundation for D2 durable quarantine)
```

---

## Constraints — What NOT to Do

These constraints apply to all waves:

1. **Do NOT break backward compatibility.** All new parameters (`raise_on_break`, `async_flush`) must default to their current-behavior values (`False`). Existing callers require zero changes.

2. **Do NOT add third-party dependencies.** The flusher uses only Python stdlib: `queue.Queue`, `threading.Thread`, `atexit`. No asyncio libraries, no external queue packages.

3. **Do NOT implement the full Langfuse MediaUploadConsumer pattern.** The flusher is `queue + thread + flush`. Not a media handling system.

4. **Do NOT implement CEL policy support.** That is explicitly deferred to D3 (ADR-010 §DEFER).

5. **Do NOT implement store persistence for `circuit_state`.** The `circuit_state` field is added to `TrustState` in Wave 1, but the logic to persist/restore circuit state on store transitions is D2 work.

6. **Do NOT create `cmd/secure-mcp/`** or any fulcrum-io changes. D2 patterns are out of scope for this wave.

7. **Do NOT refactor existing store implementations** beyond adding serialization support for the new `circuit_state` field (which may require a one-line JSON schema update in FileStore and FulcrumStore — verify and fix only if tests break).

---

## Success Criteria

Before marking this plan complete:

- [ ] `pytest tests/ -v` — all tests pass, zero failures
- [ ] `pytest tests/ --cov=fulcrum_trust --cov-report=term-missing` — 95%+ on `context.py`, `flusher.py`
- [ ] `python -c "from fulcrum_trust import TrustCircuitOpen, TrustManager; print('OK')"` — imports clean
- [ ] `TrustManager(async_flush=True)` with `FileStore` integration test passes
- [ ] Concurrent isolation test with `asyncio.gather()` passes
- [ ] `docs/api-reference.md` covers all new public surface
- [ ] `CHANGELOG.md` updated
- [ ] ADR-010 status updated from `Proposed` to `Accepted` in `docs/ADR-010-engineering-intel-adoption.md`

---

## D2 Scope (Not In This Plan)

When Phase B begins, a separate plan will cover:
- **P-06 full implementation:** Store persistence of `circuit_state` (MemoryStore, FileStore, FulcrumStore) + restore on `TrustManager` init
- **P-08:** `/.well-known/mcp-servers` discovery endpoint in new `cmd/secure-mcp-postgres/` and `cmd/secure-mcp-slack/`
- **P-05:** Governance header injection (`X-Fulcrum-Trust-Score`, `X-Fulcrum-Policy-Result`, `X-Fulcrum-Envelope-ID`)
- **`internal/securemcp/`:** Shared Secure MCP Server framework in fulcrum-io

The `circuit_state` field added in Wave 1 is the D1→D2 handoff point.
