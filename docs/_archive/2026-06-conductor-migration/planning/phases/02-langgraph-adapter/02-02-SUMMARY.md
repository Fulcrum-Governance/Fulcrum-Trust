---
phase: 02-langgraph-adapter
plan: "02"
subsystem: testing
tags: [langgraph, trust, circuit-breaker, pytest, coverage, beta-distribution, async]

# Dependency graph
requires:
  - phase: 02-langgraph-adapter
    plan: "01"
    provides: TrustAwareGraph, OutcomeClassifier, CallbackRegistry — adapter implementation to test

provides:
  - Full behavioral test suite for LangGraph adapter (24 tests, 0 failures)
  - OutcomeClassifier unit tests covering all classify() branches
  - TrustAwareGraph integration tests proving LANG-01..LANG-04 requirements
  - Adapter coverage: langgraph.py 99%, adapters/__init__.py 100%
  - Async node wrapping fix for LangGraph 0.4.x afunc path

affects: [03-demos, 04-ship]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - asyncio.get_event_loop().run_until_complete() for testing async LangGraph nodes (not pytest-asyncio — avoids asyncio mode config conflicts)
    - pragma: no cover on except ImportError defensive fallbacks for optional deps
    - Pre-seeding TrustManager with FAILURE outcomes to trigger should_terminate() before graph runs
    - _was_terminated=True direct attribute set to simulate recovery context in tests

key-files:
  created:
    - tests/test_langgraph_adapter.py
  modified:
    - fulcrum_trust/adapters/langgraph.py
    - fulcrum_trust/adapters/__init__.py

key-decisions:
  - "async nodes in LangGraph 0.4.x use afunc (not func) on RunnableCallable — _wrap_nodes must check both; fixed as Rule 1 bug"
  - "pragma: no cover on except ImportError fallbacks for RunnableLambda and _LANGGRAPH_AVAILABLE — unreachable when langgraph is installed"
  - "TrustManager(config=TrustConfig(...)) uses keyword arg — positional passes TrustConfig as store param (noted in 02-01 issues)"
  - "ainvoke required for async-only nodes — .invoke() raises TypeError in LangGraph 0.4.x"

patterns-established:
  - "Coverage-gap targeted tests: test_node_with_no_outgoing_edge and test_edges_discard_attribute_error cover otherwise-unreachable branches"
  - "Side-effect list (executed_step2=[]) pattern for asserting node did NOT execute during circuit break"

requirements-completed: [LANG-01, LANG-02, LANG-03, LANG-04]

# Metrics
duration: 8min
completed: 2026-02-19
---

# Phase 2 Plan 02: LangGraph Adapter Test Suite Summary

**24 behavioral tests prove all four LANG requirements with plain Python lambda nodes: wrapping (LANG-01), trust scoring (LANG-02), hard termination via conditional edges (LANG-03), and all three callback types (LANG-04) — plus async node fix for LangGraph 0.4.x**

## Performance

- **Duration:** 8 min
- **Started:** 2026-02-19T00:47:21Z
- **Completed:** 2026-02-19T00:55:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- 11 `TestOutcomeClassifier` unit tests cover every `classify()` branch: None, non-dict, empty dict, error/exception/traceback keys, identical long-string (PARTIAL), identical numeric (SUCCESS — Pitfall 6 validation), valid update (SUCCESS), new key (SUCCESS), unchanged list (PARTIAL)
- 13 `TestTrustAwareGraph` integration tests prove LANG-01..LANG-04 plus async node wrapping and ImportError guard
- `test_circuit_break_terminates_graph` uses a side-effect list (`executed_step2`) to assert step2 does NOT execute — confirming hard termination via conditional edge routing to END, not just callback emission
- Async node fix: `_wrap_nodes` now detects `afunc` (LangGraph 0.4.x async path) and wraps it with `RunnableCallable(None, wrapped_async)`, enabling trust evaluation after `ainvoke`
- Adapter coverage: `langgraph.py` 99%, `adapters/__init__.py` 100%; full suite: 97 tests, 96.83% core coverage

## Task Commits

Each task was committed atomically:

1. **Task 1: OutcomeClassifier unit tests** - `6066467` (test)
2. **Task 2: TrustAwareGraph integration tests + async fix** - `f640312` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `tests/test_langgraph_adapter.py` — Full 24-test suite: TestOutcomeClassifier (11) + TestTrustAwareGraph (13)
- `fulcrum_trust/adapters/langgraph.py` — Fixed `_wrap_nodes` to handle async nodes via `afunc`; added `# pragma: no cover` to unreachable ImportError fallbacks
- `fulcrum_trust/adapters/__init__.py` — Added `# pragma: no cover` to unreachable `except ImportError` block

## Decisions Made

- `asyncio.get_event_loop().run_until_complete()` chosen over `pytest.mark.asyncio` to avoid asyncio mode configuration requirements. The test stays fully synchronous from pytest's perspective while correctly awaiting `ainvoke`.
- `pragma: no cover` added to `except ImportError` fallbacks in adapters (both `__init__.py` and `langgraph.py`). These branches are unreachable in any environment where langgraph is installed — keeping them uncovered would require complex import mocking that provides no behavioral value.
- `TrustManager(config=TrustConfig(threshold=0.9))` uses keyword argument. Using positional would pass `TrustConfig` as the `store` parameter (wrong type) — discovered in 02-01 issues.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Async nodes not wrapped — afunc path missing in _wrap_nodes**
- **Found during:** Task 2 (test_async_node_is_wrapped_correctly)
- **Issue:** In LangGraph 0.4.x, async nodes are stored on `RunnableCallable` with `afunc=<coroutine>` and `func=None`. The original `_wrap_nodes` implementation only checked `func`, so async nodes were silently skipped — trust evaluation never ran after `ainvoke`. `tm.get_trust_score()` remained at 0.5 (default) after calling `ainvoke`.
- **Fix:** Added `elif original_afn is not None:` branch in `_wrap_nodes`. Wraps `afunc` with `_make_node_wrapper(original_afn)` and creates `RunnableCallable(None, wrapped_async)` — passing `None` as the sync func so LangGraph routes async invocations through the `afunc` path correctly.
- **Files modified:** `fulcrum_trust/adapters/langgraph.py`
- **Verification:** `tm.get_trust_score("a","b") != 0.5` after `ainvoke` — trust was updated, confirming wrapper ran. All mypy/ruff gates pass.
- **Committed in:** `f640312` (Task 2 commit)

**2. [Rule 3 - Blocking] Ruff UP035/UP006/I001 errors in test file**
- **Found during:** Task 2 (ruff check on test file)
- **Issue:** Plan-specified imports (`from typing import Any, Dict, List`) triggered ruff UP035 (deprecated typing aliases) and UP006 (use builtin generics). Also I001 (unsorted imports).
- **Fix:** Changed `List[...]` → `list[...]`, `Dict[...]` → `dict[...]`, removed `Dict` and `List` from imports, kept only `Any`. Ran `ruff check --fix` for import sort, `ruff format` for style.
- **Files modified:** `tests/test_langgraph_adapter.py`
- **Verification:** `ruff check` + `ruff format --check` both exit 0.
- **Committed in:** `f640312` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 × Rule 1 - Bug, 1 × Rule 3 - Blocking)
**Impact on plan:** Both fixes required for correctness and CI compliance. The async fix adds missing behavioral coverage; the ruff fix meets code style gate. No scope creep.

## Issues Encountered

- LangGraph 0.4.x stores async nodes with `afunc` (not `func`) on the `RunnableCallable` NamedTuple. This was not documented in the plan's context and required discovering through exploratory testing during Task 2.
- Coverage measurement for adapter module isolated from core: `--cov=fulcrum_trust/adapters` path notation doesn't work with the configured `omit` patterns; used temp `.coveragerc` for accurate measurement.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All four LANG requirements have behavioral proof via the test suite
- `test_circuit_break_terminates_graph` provides regression baseline for the critical hard-termination requirement
- 24 tests + 73 prior tests = 97 total tests, 96.83% core coverage — Phase 2 quality gates met
- Phase 03-demos can proceed: TrustAwareGraph is provably correct against LangGraph 0.4.5

---
*Phase: 02-langgraph-adapter*
*Completed: 2026-02-19*
