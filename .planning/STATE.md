# State — fulcrum-trust

## Current Position

**Sprint:** AOS D1 — Trust-Based Circuit Breaker (Weeks 1-4)
**Active Phase:** 03-demos
**Current Plan:** 03-01
**Ship Date:** ~March 17, 2026 (PyPI publish + blog post)

## Progress

| Phase | Plan | Name | Status |
|-------|------|------|--------|
| 01-core-trust-engine | 01-01 | Core types, evaluator, manager, stores | Complete |
| 01-core-trust-engine | 01-02 | Test suite | Complete |
| 01-core-trust-engine | 01-03 | Package infrastructure (pyproject.toml, README, CI) | Complete |
| 02-langgraph-adapter | 02-01 | TrustAwareGraph adapter implementation | Complete |
| 02-langgraph-adapter | 02-02 | LangGraph adapter test suite | Complete |

## Decisions Log

| Date | Decision | Context |
|------|----------|---------|
| 2026-02-17 | Pure Python, no Go dependency | Zero friction adoption |
| 2026-02-17 | Beta distribution trust model | Formally validated, captures uncertainty |
| 2026-02-17 | LangGraph adapter first | Largest growing framework |
| 2026-02-17 | Apache 2.0 license | Max adoption |
| 2026-02-17 | numpy optional (pure Python fallback) | Minimize dependency chain |
| 2026-02-18 | Coverage gate in both addopts and [tool.coverage.report] | Belt-and-suspenders per RESEARCH.md Pitfall 7 |
| 2026-02-18 | adapters/ excluded from 95% coverage gate | Phase 2 sets separate 90% threshold |
| 2026-02-18 | ruff format --check in CI (not --fix) | Fails on bad format; no silent auto-commits |
| 2026-02-18 | CI matrix: 3.9/3.11/3.12, fail-fast=false | 3.9 compat floor, modern coverage, skip 3.10 for speed |
| 2026-02-18 | beta_val field name (not beta) in TrustState | Avoids shadowing stdlib beta, satisfies mypy strict |
| 2026-02-18 | Decay target is prior (1.0), not 0.0 | Trust decays toward uncertainty, not distrust |
| 2026-02-18 | dataclasses.replace() for read-only decay copies | Prevents stored state mutation in get_trust_score/should_terminate |
| 2026-02-18 | Removed numpy optional branch from decay.py | Pure Python float(0.5**x) is equivalent and mypy-strict-clean |
| 2026-02-18 | Direct last_updated manipulation in decay integration test | Simulates 100 half-lives without sleeping — fast and deterministic |
| 2026-02-18 | pytest.approx(x, abs=0.05) for decay math tests | Tolerates floating-point accumulation over many simulated half-lives |
| 2026-02-19 | StateNodeSpec._replace() + RunnableCallable for node wrapping | LangGraph 0.4.x spec.runnable is read-only NamedTuple field; _replace() is only safe mutation path |
| 2026-02-19 | _make_routing_fn at module level (not inside loop) | Avoids ruff B023 loop-closure lint; also cleaner separation |
| 2026-02-19 | local Any alias pattern for internal LangGraph API access | Concentrates type suppression in one place per method instead of scattered type: ignore |
| 2026-02-19 | langgraph added to dev extras (not just langgraph extra) | CI installs it without user needing to specify the extra |
| 2026-02-19 | async nodes in LangGraph 0.4.x use afunc path (not func) on RunnableCallable | _wrap_nodes must check both; afunc=None for sync nodes, func=None for async nodes |
| 2026-02-19 | pragma: no cover on except ImportError fallbacks for optional deps | Unreachable when langgraph is installed; no behavioral value in mocking imports away |
| 2026-02-19 | ainvoke required for async-only LangGraph nodes | .invoke() raises TypeError in 0.4.x: "No synchronous function provided" |

## Blockers

None active.

## Performance Metrics

| Phase | Plan | Duration | Tasks | Files |
|-------|------|----------|-------|-------|
| 01-core-trust-engine | 01-03 | 2min | 2 | 3 |
| 01-core-trust-engine | 01-01 | 5min | 2 | 9 |
| 01-core-trust-engine | 01-02 | 2min | 2 | 6 |
| 02-langgraph-adapter | 02-01 | 10min | 2 | 3 |
| 02-langgraph-adapter | 02-02 | 8min | 2 | 3 |

## Implementation Notes

**Week 1 Plan:** Core engine
- Beta-distribution evaluator (TrustEvaluator class)
- Trust types (TrustScore, InteractionOutcome, RelationshipState)
- Memory stores (InMemoryStore, FileBackedStore)
- Time decay with configurable half-life
- 95%+ test coverage

**Week 2 Plan:** LangGraph adapter
- TrustAwareGraph wrapper
- Outcome classification
- Trust-based conditional edges
- Callback hooks

**Week 3 Plan:** Demos
- Gratitude loop ($47K incident reproduction)
- Drift detection
- Recovery scenarios

**Week 4 Plan:** Ship
- PyPI publish
- Documentation (README, API reference, mkdocs)
- Blog post
- Community distribution

## Session Notes

- Repo created: github.com/Fulcrum-Governance/fulcrum-trust (public)
- Directory scaffold in place: fulcrum_trust/, tests/, examples/, docs/
- GSD installed with quality profile
- 01-03 complete: pyproject.toml, README.md (quick-start), .github/workflows/ci.yml
- 01-01 complete: all 9 source files, mypy strict-clean, all behavioral assertions pass
- pip install -e ".[dev]" confirmed working; all dev tools (pytest, mypy, ruff) installed
- 01-02 complete: 73-test suite, 96.83% coverage, all TRUST-01..TRUST-06 requirements proven
- Phase 01 entirely done. All plans (01-01, 01-02, 01-03) complete.
- 02-01 complete: TrustAwareGraph, OutcomeClassifier, CallbackRegistry implemented
  - LangGraph 0.4.x API compatibility fixes (StateNodeSpec._replace, RunnableCallable)
  - mypy strict 0 errors, ruff all pass, 73 existing tests still green
  - Hard termination via conditional edges (LANG-03) confirmed working
- 02-02 complete: 24-test suite proving all LANG-01..LANG-04 requirements
  - async node _wrap_nodes fix (afunc path for LangGraph 0.4.x)
  - langgraph.py 99% coverage, adapters/__init__.py 100% coverage
  - 97 total tests, 96.83% core coverage, mypy/ruff all pass
- Stopped at: Completed 02-02-PLAN.md

---
*Last updated: 2026-02-19 (02-02 complete)*
