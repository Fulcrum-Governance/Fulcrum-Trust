---
phase: 02-langgraph-adapter
plan: "01"
subsystem: adapters
tags: [langgraph, trust, circuit-breaker, beta-distribution, conditional-edges]

# Dependency graph
requires:
  - phase: 01-core-trust-engine
    provides: TrustManager, TrustOutcome, TrustState, TrustConfig types and evaluation engine

provides:
  - TrustAwareGraph class wrapping uncompiled LangGraph StateGraph with trust evaluation
  - OutcomeClassifier classifying node outputs as SUCCESS / PARTIAL / FAILURE
  - CallbackRegistry for on_trust_change / on_circuit_break / on_recovery hooks
  - Conditional edge injection for hard graph termination when trust < threshold
  - langgraph optional dep group in pyproject.toml with mypy overrides

affects: [02-02, 03-demos, 04-ship]

# Tech tracking
tech-stack:
  added: [langgraph>=0.2.0, langchain_core (transitive via langgraph)]
  patterns:
    - NamedTuple._replace() for immutable StateNodeSpec mutation
    - Module-level factory function (_make_routing_fn) to avoid B023 loop-closure lint
    - local Any alias pattern for internal LangGraph API access without mypy noise
    - _LANGGRAPH_AVAILABLE guard for optional dependency import

key-files:
  created:
    - fulcrum_trust/adapters/langgraph.py
    - fulcrum_trust/adapters/__init__.py
  modified:
    - pyproject.toml

key-decisions:
  - "Use StateNodeSpec._replace() + RunnableCallable (not RunnableLambda) for node wrapping in LangGraph 0.4.x — spec.runnable is read-only; NamedTuple._replace() is the only way to update it"
  - "Module-level _make_routing_fn() avoids B023 ruff lint (function defined in loop not binding loop variable)"
  - "local Any alias (graph: Any = self._graph) concentrates internal-API type: ignore noise in one place per method"
  - "Remove END from try-block import — imported locally in _inject_termination_edges only, keeping module-level imports clean"
  - "langgraph added to dev extras so CI installs it without user needing the langgraph extra"

patterns-established:
  - "Optional-dep guard: try/except ImportError sets _LANGGRAPH_AVAILABLE; TYPE_CHECKING block for type stubs only"
  - "Internal LangGraph API access via local Any alias, not scattered type: ignore comments"

requirements-completed: [LANG-01, LANG-02, LANG-03, LANG-04]

# Metrics
duration: 10min
completed: 2026-02-19
---

# Phase 2 Plan 01: LangGraph Adapter Summary

**TrustAwareGraph wraps any uncompiled StateGraph with Beta-distribution trust evaluation, per-node callbacks, and conditional-edge hard termination routing to END when trust falls below threshold**

## Performance

- **Duration:** 10 min
- **Started:** 2026-02-19T00:33:58Z
- **Completed:** 2026-02-19T00:43:42Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- `OutcomeClassifier.classify()` correctly handles None, empty dict, error keys (`error`/`exception`/`traceback`), repetitive long-string outputs (PARTIAL), and valid dict outputs (SUCCESS)
- `TrustAwareGraph` wraps LangGraph 0.4.x StateGraph by extracting `spec.runnable.func` and using `NamedTuple._replace()` with a new `RunnableCallable` — the correct API for this version
- `compile()` injects `add_conditional_edges()` for every non-`__start__` node with a simple outgoing edge, routing to `END` when `should_terminate()` is True (hard termination, not just a callback)
- All callbacks (`on_trust_change`, `on_circuit_break`, `on_recovery`) fire at correct moments
- `mypy` strict: 0 errors across all 11 source files; `ruff` check + format: all pass; existing 73-test suite: 96.83% coverage maintained

## Task Commits

Each task was committed atomically:

1. **Task 1: OutcomeClassifier and CallbackRegistry** - `ddcace6` (feat)
2. **Task 2: TrustAwareGraph + adapters/__init__.py + pyproject.toml** - `447ee8e` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `fulcrum_trust/adapters/langgraph.py` — TrustAwareGraph, OutcomeClassifier, CallbackRegistry, _make_routing_fn (module-level factory)
- `fulcrum_trust/adapters/__init__.py` — Conditional TrustAwareGraph export guarded by _LANGGRAPH_AVAILABLE
- `pyproject.toml` — langgraph optional dep group, langgraph dev dep, langgraph.* + langchain_core.* mypy overrides

## Decisions Made

- `spec.runnable` is a read-only NamedTuple field in LangGraph 0.4.x (StateNodeSpec). The plan's original approach (`spec.runnable = RunnableLambda(wrapped)`) raises `AttributeError: can't set attribute`. Fixed by using `spec._replace(runnable=new_runnable)` with `RunnableCallable` from `langgraph.utils.runnable`.
- `_make_routing_fn` moved to module level to avoid ruff B023 ("function definition does not bind loop variable") — the function was defined inside the `for node_name in node_names:` loop.
- `END` removed from module-level try/except import since it's only used inside `_inject_termination_edges()` where it's imported directly.
- `local Any alias` pattern (`graph: Any = self._graph`) adopted for the two methods that access LangGraph internals — keeps `type: ignore` concentrated and makes it obvious where internal-API access occurs.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Node wrapping API incompatible with LangGraph 0.4.x**
- **Found during:** Task 2 (TrustAwareGraph.compile() implementation)
- **Issue:** Plan specified `spec.runnable = RunnableLambda(wrapped)` and `from langchain_core.runnables import RunnableLambda`. In LangGraph 0.4.x, `StateNodeSpec.runnable` is a read-only NamedTuple field; direct assignment raises `AttributeError: can't set attribute`. `RunnableLambda` also has type incompatibilities with what LangGraph expects.
- **Fix:** Used `spec._replace(runnable=RunnableCallable(wrapped))` where `RunnableCallable` is imported from `langgraph.utils.runnable` (LangGraph's own native callable type with correct async dispatch). Fallback to `RunnableLambda` retained if `RunnableCallable` not available.
- **Files modified:** `fulcrum_trust/adapters/langgraph.py`
- **Verification:** Both normal run (count==1, callback fired) and termination test (circuit_break fired) pass.
- **Committed in:** `447ee8e` (Task 2 commit)

**2. [Rule 1 - Bug] _make_routing_fn defined inside loop triggering B023**
- **Found during:** Task 2 (ruff check)
- **Issue:** `_make_routing_fn` was defined inside the `for node_name in node_names:` loop, causing ruff B023 "function definition does not bind loop variable `routing_fn`".
- **Fix:** Moved `_make_routing_fn` to module level with `trust_manager`, `agent_a`, `agent_b`, `normal_next` as explicit parameters (already the correct pattern for closure safety).
- **Files modified:** `fulcrum_trust/adapters/langgraph.py`
- **Verification:** `ruff check` passes with 0 errors.
- **Committed in:** `447ee8e` (Task 2 commit)

**3. [Rule 1 - Bug] Multiple stale `type: ignore` comments causing mypy errors**
- **Found during:** Task 2 (mypy run)
- **Issue:** LangGraph 0.4.x ships with type stubs, so `type: ignore[import-untyped]` annotations on langgraph imports were flagged as `[unused-ignore]`. Plan-specified annotations assumed langgraph was untyped.
- **Fix:** Removed `type: ignore[import-untyped]` from try/except and TYPE_CHECKING imports. Added `langgraph.*` and `langchain_core.*` mypy overrides to `pyproject.toml`. Used `local Any alias` pattern for internal-API access in `_wrap_nodes()` and `_inject_termination_edges()`.
- **Files modified:** `fulcrum_trust/adapters/langgraph.py`, `pyproject.toml`
- **Verification:** `mypy fulcrum_trust/` exits 0 with "Success: no issues found in 11 source files".
- **Committed in:** `447ee8e` (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (3 × Rule 1 - Bug)
**Impact on plan:** All auto-fixes required for LangGraph 0.4.x compatibility and mypy/ruff compliance. No scope creep. All plan requirements (LANG-01..LANG-04) delivered as specified.

## Issues Encountered

- LangGraph version skew: plan was written for 0.2.x internal API; installed version is 0.4.5. `StateNodeSpec` changed from a mutable dataclass to an immutable NamedTuple between these versions. Required using `_replace()` pattern.
- The `TrustManager(TrustConfig(threshold=0.9))` call in the plan's verification script passes `TrustConfig` as the `store` argument (positional) — would fail at runtime. Corrected in testing to `TrustManager(config=TrustConfig(threshold=0.9))`.

## User Setup Required

None - no external service configuration required. `langgraph` is installed as a dev dependency via `pip install -e ".[dev]"`.

## Next Phase Readiness

- `TrustAwareGraph` is complete and tested against real LangGraph 0.4.5
- `OutcomeClassifier` and `CallbackRegistry` are self-contained and reusable
- Plan 02-02 (test suite for the adapter) can proceed immediately
- The `_wrap_nodes()` and `_inject_termination_edges()` methods are well-isolated for unit testing

---
*Phase: 02-langgraph-adapter*
*Completed: 2026-02-19*
