---
phase: 03-demos-content
plan: "01"
subsystem: examples
tags: [demos, cli, visualization, trust-lifecycle]
dependency_graph:
  requires:
    - fulcrum_trust.TrustManager
    - fulcrum_trust.TrustOutcome
    - fulcrum_trust.TrustConfig
    - fulcrum_trust.types.TrustState
  provides:
    - examples/gratitude_loop.py
    - examples/drift_detection.py
    - examples/recovery.py
  affects: []
tech_stack:
  added: []
  patterns:
    - ANSI terminal colour output (inline constants, no library)
    - argparse mutually-exclusive flag group (--with-trust / --without-trust)
    - Beta distribution trust scoring visualised per-iteration
key_files:
  created:
    - examples/gratitude_loop.py
    - examples/drift_detection.py
    - examples/recovery.py
  modified: []
decisions:
  - DECAY_PER_ITER raised to 0.015 (from planned 0.012) so drift_detection.py breaks at iter 85 (before 90 limit)
  - threshold=0.4 retained for drift demo; threshold increase to 0.45 not needed once decay rate was adjusted
metrics:
  duration: 3min
  tasks_completed: 3
  tasks_total: 3
  files_created: 3
  files_modified: 0
  completed_date: "2026-02-18"
---

# Phase 03 Plan 01: Demo Scripts Summary

**One-liner:** Three runnable demos proving trust circuit breaking — gratitude loop (terminates at iter 5), drift detection (fires at iter 85), and three-phase recovery arc — all using TrustManager directly with stdlib + fulcrum_trust only.

## Tasks Completed

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | Gratitude Loop Demo (DEMO-01) | 6c49901 | examples/gratitude_loop.py |
| 2 | Drift Detection Demo (DEMO-02) | ab3d5d6 | examples/drift_detection.py |
| 3 | Recovery Demo (DEMO-03) | c617c58 | examples/recovery.py |

## What Was Built

### DEMO-01: examples/gratitude_loop.py

Two agents in an endless mutual-praise loop. `--with-trust` uses `TrustConfig(partial_alpha_weight=0.2, partial_beta_weight=0.8)` so each PARTIAL interaction grows beta 4x faster than alpha. Trust drops below the 0.3 threshold at iteration 4 (the 5th call) — breaking within 15 iterations as required. `--without-trust` runs all 50 iterations with no stop condition, showing the runaway problem.

### DEMO-02: examples/drift_detection.py

An agent degrades at 1.5%/iteration across 120 iterations. Quality starts healthy (SUCCESS), enters the PARTIAL zone at ~iter 20, and the FAILURE zone at ~iter 47. Despite 20 strong SUCCESS interactions building alpha to 21, the accumulating FAILUREs after iter 47 drive trust below the 0.4 threshold at iteration 85 — 35 iterations before the maximum.

### DEMO-03: examples/recovery.py

Three explicit phases:
- **DEGRADATION**: 2 FAILURE outcomes drop trust from 0.5 to 0.25 (< 0.3 threshold); circuit opens.
- **INTERVENTION**: `mgr.reset()` deletes the pair's state; `get_trust_score()` returns the uninformative prior of 0.500.
- **RECOVERY**: 15 SUCCESS outcomes rebuild trust to 0.941 (alpha=16, beta=1). Final score well above the 0.5 "fully restored" marker.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Parameter Adjustment] DECAY_PER_ITER increased from 0.012 to 0.015**

- **Found during:** Task 2 verification
- **Issue:** With DECAY_PER_ITER=0.012, trust dropped below 0.4 at iteration 106, not before the required iteration 90. The plan explicitly anticipated this and instructed the executor to "increase DECAY_PER_ITER to 0.015" if needed.
- **Fix:** Changed DECAY_PER_ITER from 0.012 to 0.015. Updated docstring iteration estimates (PARTIAL at ~20, FAILURE at ~47). Circuit now breaks at iteration 85.
- **Files modified:** examples/drift_detection.py
- **Commit:** ab3d5d6 (adjustment made inline before commit)

## Self-Check: PASSED

| Item | Status |
|------|--------|
| examples/gratitude_loop.py | FOUND |
| examples/drift_detection.py | FOUND |
| examples/recovery.py | FOUND |
| .planning/phases/03-demos-content/03-01-SUMMARY.md | FOUND |
| Commit 6c49901 (gratitude_loop) | FOUND |
| Commit ab3d5d6 (drift_detection) | FOUND |
| Commit c617c58 (recovery) | FOUND |
