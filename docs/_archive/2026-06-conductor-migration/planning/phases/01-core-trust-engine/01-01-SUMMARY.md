---
phase: 01-core-trust-engine
plan: "01"
subsystem: core
tags: [beta-distribution, trust-scoring, circuit-breaker, bayesian, pure-python]

# Dependency graph
requires: []
provides:
  - "TrustOutcome enum (SUCCESS/FAILURE/PARTIAL)"
  - "TrustState dataclass with Beta(alpha,beta) scoring and trust_score property"
  - "TrustConfig dataclass with configurable threshold, half-life, and prior weights"
  - "TrustEvaluator: Bayesian update with order-independent pair IDs"
  - "apply_decay(): exponential decay toward uninformative prior (1.0), not 0.0"
  - "TrustStore Protocol (structural subtyping, runtime_checkable)"
  - "MemoryStore: in-memory dict-backed store"
  - "FileStore: JSON file-backed store with empty-file safety"
  - "TrustManager: orchestrates evaluator + store + decay"
  - "Public API: TrustManager, TrustOutcome, TrustState, TrustConfig, MemoryStore, FileStore"
affects: [02-langgraph-adapter, 01-02-tests, demos]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Beta(alpha,beta) distribution trust model: T = alpha / (alpha + beta)"
    - "Lazy decay on read: decay applied before update in evaluate(), copy-on-read in get_trust_score()"
    - "Order-independent pair IDs: SHA256(sorted(a, b))[:16]"
    - "Protocol structural subtyping for TrustStore interface"
    - "dataclasses.replace() for read-only state copies to prevent mutation"

key-files:
  created:
    - fulcrum_trust/types.py
    - fulcrum_trust/evaluator.py
    - fulcrum_trust/decay.py
    - fulcrum_trust/stores/__init__.py
    - fulcrum_trust/stores/base.py
    - fulcrum_trust/stores/memory.py
    - fulcrum_trust/stores/file.py
    - fulcrum_trust/manager.py
    - fulcrum_trust/__init__.py
  modified: []

key-decisions:
  - "Use beta_val field name (not beta) to avoid shadowing stdlib beta and satisfy mypy strict"
  - "Decay target is prior (1.0), not 0.0 — trust decays toward uninformative prior, not distrust"
  - "dataclasses.replace() copy before read-only decay prevents stored state mutation"
  - "Pure Python 0.5^x fallback only — numpy branch removed for mypy strict compliance"
  - "FileStore handles empty files gracefully (tempfile creates empty files)"

patterns-established:
  - "Lazy decay pattern: apply_decay() called at start of evaluate() before recording new outcome"
  - "Read-only decay: copy state with dataclasses.replace() before apply_decay() in non-mutating methods"
  - "All state mutations go through TrustManager — single source of truth"

requirements-completed: [TRUST-01, TRUST-02, TRUST-03, TRUST-04, TRUST-05, TRUST-06]

# Metrics
duration: 5min
completed: 2026-02-18
---

# Phase 01 Plan 01: Core Trust Engine — Types, Evaluator, Decay, Stores, Manager Summary

**Beta(alpha,beta) trust engine with Bayesian updates, exponential decay toward prior (not zero), order-independent pair IDs, MemoryStore, JSON FileStore, and TrustManager orchestrator**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-18T23:14:01Z
- **Completed:** 2026-02-18T23:19:26Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments

- Complete trust engine in 9 pure-Python source files with zero external dependencies
- Beta distribution trust scoring: `T = alpha / (alpha + beta)`, uninformative prior yields 0.5
- Circuit breaking: two FAILURE outcomes drop trust to 0.25, triggering `should_terminate()` at 0.3 threshold
- Exponential decay toward uninformative prior (1.0) — trust recovers to 0.5 over time, not to zero
- FileStore survives write-read round-trip across fresh TrustManager instances
- Zero mypy errors in strict mode across all 9 source files

## Task Commits

Each task was committed atomically:

1. **Task 1: Types, Evaluator, and Decay modules** - `7007a54` (feat)
2. **Task 2: Stores and TrustManager** - `8976c7b` (feat)

**Plan metadata:** (final commit — see below)

## Files Created/Modified

- `fulcrum_trust/types.py` — TrustOutcome enum, TrustState dataclass, TrustConfig with validation
- `fulcrum_trust/evaluator.py` — TrustEvaluator with Bayesian update and SHA256 pair IDs
- `fulcrum_trust/decay.py` — apply_decay() with exponential decay toward prior=1.0
- `fulcrum_trust/stores/base.py` — TrustStore Protocol (runtime_checkable structural subtyping)
- `fulcrum_trust/stores/memory.py` — MemoryStore in-memory dict implementation
- `fulcrum_trust/stores/file.py` — FileStore JSON-backed implementation with empty-file safety
- `fulcrum_trust/stores/__init__.py` — Re-exports TrustStore, MemoryStore, FileStore
- `fulcrum_trust/manager.py` — TrustManager orchestrating evaluator + store + decay
- `fulcrum_trust/__init__.py` — Public API with __version__ = "0.1.0"

## Decisions Made

- Used `beta_val` field name (not `beta`) to avoid shadowing stdlib `beta` and satisfy mypy strict
- Decay target is `1.0` (prior), not `0.0` — trust decays toward uncertainty, not toward distrust
- Read-only decay uses `dataclasses.replace()` copy to prevent mutation of stored state objects
- Removed numpy optional branch from `decay.py` — pure Python `float(0.5 ** x)` is equivalent and avoids mypy strict errors from the try/except import pattern

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `get_trust_score` mutated stored state via apply_decay on MemoryStore reference**
- **Found during:** Task 2 (verification — order-independent pair equality check)
- **Issue:** `MemoryStore.get()` returns the stored object reference; `apply_decay` mutates in-place; successive calls to `get_trust_score` on the same pair returned different values
- **Fix:** Added `import dataclasses` and used `dataclasses.replace(state)` before calling `apply_decay` in `get_trust_score` and `should_terminate` (both read-only paths)
- **Files modified:** `fulcrum_trust/manager.py`
- **Verification:** `tm.get_trust_score('x','y') ≈ tm.get_trust_score('y','x')` within 1e-6
- **Committed in:** `8976c7b` (Task 2 commit)

**2. [Rule 1 - Bug] FileStore._load() crashed on empty files (JSONDecodeError)**
- **Found during:** Task 2 (FileStore round-trip test with tempfile.NamedTemporaryFile)
- **Issue:** `tempfile.NamedTemporaryFile` creates the file before FileStore init; `_load()` called `json.load()` on empty file, raising JSONDecodeError
- **Fix:** Read content as string first, check if empty, return empty dict if so
- **Files modified:** `fulcrum_trust/stores/file.py`
- **Verification:** FileStore round-trip test passes end-to-end
- **Committed in:** `8976c7b` (Task 2 commit)

**3. [Rule 1 - Bug] decay.py numpy optional branch caused mypy strict errors**
- **Found during:** Task 2 (mypy verification)
- **Issue:** `try: import numpy` pattern yields `unused type: ignore` when numpy absent and `no-any-return` for the float cast; both errors blocked mypy strict compliance
- **Fix:** Removed numpy branch entirely; pure Python `float(0.5 ** (elapsed / half_life))` is mathematically equivalent and mypy-clean
- **Files modified:** `fulcrum_trust/decay.py`
- **Verification:** `mypy fulcrum_trust/ --ignore-missing-imports` reports "Success: no issues found in 9 source files"
- **Committed in:** `8976c7b` (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (all Rule 1 — bugs found during verification)
**Impact on plan:** All fixes necessary for correctness and mypy compliance. No scope creep.

## Issues Encountered

- Verification script used `==` for comparing two successive `get_trust_score` calls, which fails due to `time.time()` advancing nanoseconds between calls. This is expected behavior for a time-based decay system. The implementation is correctly symmetric (same pair_id for both orderings); approximate equality `abs(diff) < 1e-6` confirms correctness.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- All 9 source files complete and mypy-strict-clean
- Public API (`from fulcrum_trust import TrustManager`) works with `PYTHONPATH=.`
- Ready for test suite implementation (01-02-PLAN.md)
- Ready for LangGraph adapter (02-x plans)
- FileStore ready for cross-session trust persistence

---
*Phase: 01-core-trust-engine*
*Completed: 2026-02-18*
