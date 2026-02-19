# Roadmap: fulcrum-trust

## Overview

Build and ship a pure Python package that provides trust-based circuit breaking for multi-agent AI systems. Starting from scaffolded repo, implement the Beta(α,β) trust engine, wrap LangGraph graphs with trust evaluation, build three demo scenarios proving the thesis, and publish v0.1.0 to PyPI with community distribution. Four phases, four weeks, ship date March 17, 2026.

## Phases

- [x] **Phase 1: Core Trust Engine** - Beta(α,β) evaluator, stores, decay — 95%+ coverage (completed 2026-02-18)
- [x] **Phase 2: LangGraph Adapter** - TrustAwareGraph wrapper with outcome classification and circuit breaking (completed 2026-02-19)
- [x] **Phase 3: Demos + Content** - Three runnable demos proving the thesis, blog post draft (completed 2026-02-19)
- [ ] **Phase 4: Ship + Distribute** - PyPI publish, CI/CD, README polish, community distribution

## Phase Details

### Phase 1: Core Trust Engine
**Goal**: TrustManager evaluates trust using Beta distribution, stores agent-pair state, decays over time, breaks circuit at threshold. 95%+ test coverage.
**Depends on**: Nothing (first phase)
**Requirements**: TRUST-01, TRUST-02, TRUST-03, TRUST-04, TRUST-05, TRUST-06
**Success Criteria** (what must be TRUE):
  1. `pip install -e .` succeeds from project root
  2. `pytest -v --cov=fulcrum_trust` passes with ≥95% coverage on all core modules
  3. `python -c "from fulcrum_trust import TrustManager; print(TrustManager().get_trust_score('a','b'))"` prints `0.5`
  4. TrustManager.should_terminate() returns True after sufficient negative outcomes
  5. Trust score decays toward 0.5 (uncertainty) after time passes without interactions
**Plans**: 3 plans

Plans:
- [ ] 01-01-PLAN.md — Core types, evaluator, stores, decay, and TrustManager source modules
- [ ] 01-02-PLAN.md — Test suite with >=95% coverage (types, evaluator, decay, stores, manager)
- [ ] 01-03-PLAN.md — Package scaffolding: pyproject.toml, CI workflow, README skeleton

### Phase 2: LangGraph Adapter
**Goal**: TrustAwareGraph wraps any LangGraph StateGraph with automatic trust evaluation at node boundaries. Terminates graphs when trust degrades.
**Depends on**: Phase 1
**Requirements**: LANG-01, LANG-02, LANG-03, LANG-04
**Success Criteria** (what must be TRUE):
  1. `TrustAwareGraph(graph, trust_manager)` wraps an existing graph with zero changes to graph code
  2. Outcome classifier detects repetitive, empty, and error-pattern outputs
  3. Wrapped graph terminates automatically when trust drops below threshold
  4. `on_circuit_break` callback fires with trust context when circuit opens
  5. `pytest tests/test_langgraph_adapter.py -v` passes
**Plans**: 2 plans

Plans:
- [ ] 02-01-PLAN.md — TrustAwareGraph wrapper, OutcomeClassifier, CallbackRegistry + pyproject.toml langgraph dep
- [ ] 02-02-PLAN.md — LangGraph adapter integration + unit tests, coverage gate

### Phase 3: Demos + Content
**Goal**: Three runnable demos that prove the thesis. Blog post draft ready for review.
**Depends on**: Phase 2
**Requirements**: DEMO-01, DEMO-02, DEMO-03
**Success Criteria** (what must be TRUE):
  1. `python examples/gratitude_loop.py --with-trust` terminates within 15 iterations, prints trust scores
  2. `python examples/gratitude_loop.py --without-trust` runs all iterations (proves the problem)
  3. `python examples/drift_detection.py` detects gradual quality degradation and terminates
  4. `python examples/recovery.py` shows trust rebuilding after circuit break
  5. `docs/blog-trust-circuit-breaker.md` exists and reviewed once
**Plans**: 2 plans

Plans:
- [ ] 03-01-PLAN.md — Three demo scripts: gratitude_loop.py (DEMO-01), drift_detection.py (DEMO-02), recovery.py (DEMO-03)
- [ ] 03-02-PLAN.md — Blog post draft: docs/blog-trust-circuit-breaker.md (1800-2200 words, $47K hook, Beta math, limitations)

### Phase 4: Ship + Distribute
**Goal**: v0.1.0 published on PyPI. GitHub release tagged. Community distribution started. Install count tracking active.
**Depends on**: Phase 3
**Requirements**: DIST-01, DIST-02, DIST-03, DIST-04, DIST-05
**Success Criteria** (what must be TRUE):
  1. `pip install fulcrum-trust` works from clean virtualenv
  2. `python -c "from fulcrum_trust import TrustManager; print('OK')"` prints OK with no errors
  3. GitHub release v0.1.0 tagged with CHANGELOG.md
  4. Blog post published (not just draft)
  5. HN Show post + Reddit posts live, pypistats.org tracking active
**Plans**: 4 plans

Plans:
- [ ] 04-01: Package polish — mypy strict, docstrings, CHANGELOG.md, CONTRIBUTING.md, API reference
- [ ] 04-02: CI/CD workflows — ci.yml (lint+test+typecheck on PR), publish.yml (PyPI on tag)
- [ ] 04-03: PyPI publish — TestPyPI dry run → fix → real publish → GitHub release
- [ ] 04-04: Community distribution — HN, r/Python, r/LangChain, AI Discord, awesome-langgraph PRs

## Progress

**Execution Order:** 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Core Trust Engine | 0/3 | Complete    | 2026-02-18 |
| 2. LangGraph Adapter | 0/2 | Complete    | 2026-02-19 |
| 3. Demos + Content | 0/2 | Complete    | 2026-02-19 |
| 4. Ship + Distribute | 0/4 | Not started | - |
