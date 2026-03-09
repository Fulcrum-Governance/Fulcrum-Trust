# fulcrum-trust — CLAUDE.md

## Project Overview
Trust-based circuit breaking for multi-agent AI systems. Pure Python package, Apache 2.0.
Part of the Fulcrum AOS (Agentic Operating System) ecosystem.

## Commands
```bash
# Development
pip install -e ".[dev]"     # Install with dev dependencies
pytest                       # Run tests
pytest --cov                 # Run with coverage
mypy fulcrum_trust/ --ignore-missing-imports  # Type checking (CI flags)
ruff check .                 # Lint
ruff format .                # Format

# Build & publish
python -m build              # Build sdist + wheel
twine check dist/*           # Validate package
twine upload dist/*          # Upload to PyPI
```

## Architecture
```
fulcrum_trust/
├── __init__.py              # Public API exports
├── types.py                 # TrustState, TrustOutcome, TrustConfig, CircuitBreakerState
├── evaluator.py             # TrustEvaluator — Beta(α,β) trust scoring
├── manager.py               # TrustManager — orchestrates evaluation + storage + decay
├── decay.py                 # Time-weighted exponential decay
├── rlm/                     # Phase 5 long-context prototype (handles, runtime, benchmark)
├── stores/
│   ├── __init__.py
│   ├── base.py              # Abstract TrustStore interface
│   ├── memory.py            # In-memory dict store
│   └── file.py              # JSON file-backed store
└── adapters/
    ├── __init__.py
    └── langgraph.py         # TrustAwareGraph wrapper
```

## Conventions
- **Type hints everywhere** — mypy strict, no `Any` without justification
- **Docstrings** — Google style on all public classes/methods
- **Test naming** — `test_{module}/test_{function}_{scenario}.py`
- **Test location** — `tests/` mirrors `fulcrum_trust/` structure
- **No heavy deps** — numpy optional (pure Python fallback), no torch/tensorflow
- **Python 3.9+** — no walrus operator in critical paths, use `from __future__ import annotations`
- **Imports** — absolute imports only (`from fulcrum_trust.types import TrustState`)

## Key Design Decisions
- Beta distribution for trust: `T(α,β) = α / (α + β)` — captures uncertainty, not just score
- Circuit break at 0.3 threshold (configurable) — formal termination guarantee
- Store interface is abstract — memory store ships first, Redis/SQL stores later
- LangGraph adapter wraps StateGraph — zero changes to user's existing graph code
- All state mutations go through TrustManager — single source of truth

## Quality Gates
- 95%+ coverage on core (types, evaluator, manager, decay, stores)
- 90%+ coverage on adapters
- Zero mypy errors in strict mode
- All public APIs have docstrings + type hints
- No dependencies beyond numpy (optional) for core
