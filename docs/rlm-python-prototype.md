# RLM Python Prototype

**Status:** Phase 5 prototype complete
**Branch:** `feat/rlm-python-prototype`
**Package:** `fulcrum_trust/rlm/`

## Goal

Prove that an RLM-style loop can navigate 100K+ token governance histories without truncation, recover a gratitude-loop signal hidden in the middle of context, and beat a conventional head-tail baseline.

## What Shipped

- `context.py` — token-budget enforcement plus symbolic-handle partitioning (`ctx://<session>/<index>`)
- `runtime.py` — restricted `peek` and `llm_batch` primitives for generated navigation programs
- `prototype.py` — deterministic gratitude-loop detector, mutable answer updates, and read → analyze → report orchestration
- `fixtures.py` — deterministic 100K+ token synthetic session generator with planted middle-context gratitude loops

## Acceptance Evidence

| Requirement | Evidence | Result |
|-------------|----------|--------|
| Process 100K+ tokens without truncation | `generate_gratitude_loop_fixture(target_tokens=110_000)` + `externalize_context()` | PASS — sample fixture externalizes `110000` tokens into `54` partitions |
| Detect planted middle-context gratitude loop | `RLMPrototype.analyze()` on fixture at `pattern_position=0.65` | PASS — detected signal at `ctx://doc-sample/0034` with score `177.5` |
| Raise `ContextExhausted` beyond 128k budget | `externalize_context(build_neutral_history(128_500), token_budget=128_000)` | PASS |
| Complete read → analyze → report chain without human intervention | `PrototypeResult.tool_chain` | PASS — returns `("read", "analyze", "report")` |
| Beat standard baseline on middle-position recall | `benchmark_middle_position_recall()` | PASS — prototype `1.0` vs baseline `0.0` across five fixtures |

## Benchmark Summary

The shipped benchmark uses five fixtures with the gratitude-loop signal planted at positions `0.2`, `0.35`, `0.5`, `0.65`, and `0.8` within the session.

- **Prototype recall:** `1.0`
- **Baseline recall:** `0.0`
- **Baseline model:** deterministic head-tail window that approximates lost-in-the-middle behavior without requiring external LLM dependencies

## Design Notes

- The prototype keeps the runtime dependency-light: pure Python, no remote model calls, and no heavyweight ML libraries.
- `llm_batch` is simulated with deterministic scoring and `ThreadPoolExecutor`, which preserves the architectural shape of parallel sub-instance dispatch.
- The mutable answer starts as `{"content": "", "ready": False}` and is updated in-place by the navigation program after candidate handles are scored.

## Follow-On Implication

This prototype proves the Python-side concept and de-risks the Go-side Phase 2b work: the future production runtime only needs to swap the restricted execution engine while keeping the handle-based navigation contract intact.
