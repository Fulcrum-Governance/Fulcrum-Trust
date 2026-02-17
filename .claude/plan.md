# fulcrum-trust — Implementation Plan
## Phased Build Plan Derived from Discovery + Research
**Created:** February 17, 2026 | **Timeline:** 4 weeks

---

## Overview

Build a Python package (`fulcrum-trust`) that provides trust-based circuit breaking for multi-agent AI systems. The package implements Beta-distribution trust degradation with formal termination guarantees. Primary integration target: LangGraph.

**Guiding principles:**
- Ship something useful in Week 1 (core library, no framework dependency)
- Framework adapters are optional imports, not requirements
- Zero backend dependency for basic usage
- Every week produces a testable, demoable artifact

---

## Phase 1: Core Trust Engine (Week 1)

### 1.1 Core Types + Trust Evaluator
- `fulcrum_trust/core.py` — TrustOutcome enum, TrustState dataclass, TrustConfig dataclass
- `fulcrum_trust/evaluator.py` — TrustManager class
  - `evaluate(agent_a, agent_b, outcome) → TrustState`
  - `should_terminate(agent_a, agent_b) → bool`
  - `get_trust_score(agent_a, agent_b) → float`
  - `pair_id(agent_a, agent_b) → str` (order-independent SHA256)
- `fulcrum_trust/store.py` — MemoryStore (in-memory dict, default)
- `fulcrum_trust/decay.py` — Time-weighted exponential decay

### 1.2 Tests
- `tests/test_core.py` — Type validation, serialization
- `tests/test_evaluator.py` — Beta computation, degradation, recovery, termination
- `tests/test_store.py` — MemoryStore CRUD, pair lookup
- `tests/test_decay.py` — Time decay accuracy
- `tests/test_parity.py` — Cross-check: Python output matches expected Go output for identical inputs

### 1.3 Package Scaffolding
- `pyproject.toml` — Build config (hatchling), metadata, Python ≥3.10
- `fulcrum_trust/__init__.py` — Public API exports
- `README.md` — Package description, install, quickstart
- `LICENSE` — Apache 2.0
- `.gitignore`, `.github/workflows/ci.yml`

**Exit criteria:**
```bash
pip install -e .
pytest -v --cov=fulcrum_trust --cov-report=term-missing
# All tests pass, ≥95% coverage
python -c "from fulcrum_trust import TrustManager; tm = TrustManager(); print(tm.get_trust_score('a','b'))"
# Prints: 0.5
```

---

## Phase 2: LangGraph Adapter + Envelope Bridge (Week 2)

### 2.1 LangGraph Adapter
- `fulcrum_trust/adapters/langgraph.py` — TrustAwareGraph class
  - Wraps LangGraph StateGraph
  - Injects trust evaluation at state transitions
  - Configurable: threshold, decay, outcome classifier
  - Automatic agent pair extraction from state
- `fulcrum_trust/adapters/__init__.py`

### 2.2 Outcome Classifier
- `fulcrum_trust/classifier.py` — Heuristic outcome classification
  - Detect repetitive outputs (cosine similarity or exact match)
  - Detect empty/trivial responses
  - Detect error patterns
  - Pluggable: user can provide custom classifier

### 2.3 Tests
- `tests/test_langgraph_adapter.py` — Wrap/unwrap, trust injection, termination
- `tests/test_classifier.py` — Pattern detection accuracy

**Exit criteria:**
```bash
pytest tests/test_langgraph_adapter.py -v
# LangGraph adapter wraps graph, injects trust, terminates on degradation
```

---

## Phase 3: Demos + Content (Week 3)

### 3.1 Gratitude Loop Demo
- `examples/gratitude_loop.py`
  - Two LangGraph agents: Analyzer, Verifier
  - Mode 1: `--without-trust` → infinite loop (capped at 50 iterations for safety)
  - Mode 2: `--with-trust` → terminates at ~iteration 8-12
  - Side-by-side cost comparison output
  - Trust score printed at each iteration

### 3.2 Drift Detection Demo
- `examples/drift_detection.py`
  - Agent gradually produces lower quality output
  - Trust detects degradation trend
  - Terminates before quality becomes harmful

### 3.3 Recovery Demo
- `examples/recovery.py`
  - Agent pair fails, trust degrades
  - Intervention improves quality
  - Trust recovers, collaboration continues

### 3.4 Blog Post Draft
- `docs/blog-trust-circuit-breaker.md`
  - The problem (cite MAST, $47K incident)
  - The math (Beta distribution, kept accessible)
  - The demo (before/after, with code)
  - The code (pip install, 5-line integration)
  - The vision (teaser for AOS)

**Exit criteria:**
```bash
cd examples
python gratitude_loop.py --with-trust
# Terminates within 15 iterations, prints trust scores
python gratitude_loop.py --without-trust --max-iterations=30
# Runs all 30 iterations
```

---

## Phase 4: Ship + Distribute (Week 4)

### 4.1 Package Polish
- Type hints on all public methods (mypy strict)
- Docstrings (Google style) on all public classes/methods
- `CHANGELOG.md` v0.1.0
- `CONTRIBUTING.md`
- `docs/api-reference.md`

### 4.2 CI/CD
- `.github/workflows/ci.yml` — pytest + mypy + ruff on PR
- `.github/workflows/publish.yml` — PyPI publish on tag

### 4.3 Publish
- TestPyPI first → verify install from clean venv
- PyPI publish: `fulcrum-trust==0.1.0`
- GitHub release with changelog

### 4.4 Distribution
- Submit to LangGraph community (Discord, GitHub discussions)
- Post to Hacker News (Show HN)
- Post to r/MachineLearning, r/LangChain
- Tweet thread with demo GIF/terminal recording
- Submit to awesome-langgraph lists

### 4.5 Measurement
- PyPI download tracking (pypistats.org)
- GitHub star + fork tracking
- Issue/discussion monitoring
- Blog post analytics

**Exit criteria:**
```bash
pip install fulcrum-trust
python -c "from fulcrum_trust import TrustManager; print('OK')"
# Works from clean virtualenv, no errors
```

---

## Dependencies

| Package | Required | Phase |
|---------|----------|-------|
| Python ≥3.10 | ✅ Core | 1 |
| pytest | Dev only | 1 |
| pytest-cov | Dev only | 1 |
| mypy | Dev only | 4 |
| ruff | Dev only | 4 |
| langgraph | Optional (adapter) | 2 |
| redis | Optional (persistent store) | Future |

---

## File Structure (Target)

```
fulcrum-trust/
├── .claude/
│   ├── discovery.md
│   ├── research.md
│   ├── plan.md          ← this file
│   └── progress.md
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── publish.yml
├── fulcrum_trust/
│   ├── __init__.py
│   ├── core.py          # Types: TrustOutcome, TrustState, TrustConfig
│   ├── evaluator.py     # TrustManager
│   ├── store.py         # MemoryStore (default), RedisStore (optional)
│   ├── decay.py         # Time-weighted decay
│   ├── classifier.py    # Outcome classification heuristics
│   └── adapters/
│       ├── __init__.py
│       └── langgraph.py # TrustAwareGraph
├── tests/
│   ├── test_core.py
│   ├── test_evaluator.py
│   ├── test_store.py
│   ├── test_decay.py
│   ├── test_parity.py
│   ├── test_classifier.py
│   └── test_langgraph_adapter.py
├── examples/
│   ├── gratitude_loop.py
│   ├── drift_detection.py
│   └── recovery.py
├── docs/
│   ├── api-reference.md
│   └── blog-trust-circuit-breaker.md
├── pyproject.toml
├── README.md
├── LICENSE
├── CHANGELOG.md
└── CONTRIBUTING.md
```

---

*Plan v1.0 — February 17, 2026*
*Derived from: discovery.md, research.md, Fulcrum AOS Phase 1 spec*
