# fulcrum-trust — CLAUDE.md

## Project Overview
Trust-based circuit breaking for multi-agent AI systems. Pure Python package, Apache 2.0.
Part of the Fulcrum governance-kernel ecosystem.

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
├── __init__.py              # Public API exports (all public symbols)
├── types.py                 # TrustState, TrustOutcome, TrustConfig, TrustCircuitOpen
├── evaluator.py             # TrustEvaluator — Beta(α,β) trust scoring, MakePairID
├── manager.py               # TrustManager — orchestrates evaluation + storage + decay + IPC
│                            #   evaluate(), terminate(), get_trust_score(), should_terminate()
├── decay.py                 # Time-weighted exponential decay toward prior (1.0)
├── context.py               # ContextVar-based execution isolation (concurrent evaluations)
├── flusher.py               # BackgroundFlusher — thread-safe async store batching
├── ipc/                     # Cross-process trust state synchronization
│   ├── __init__.py
│   ├── bridge.py            # CircuitState enum (0-3), IPCBridge protocol, NullBridge
│   └── redis_bridge.py      # RedisIPCBridge — atomic Redis writes + optional NATS telemetry
├── rlm/                     # RLM long-context prototype (handles, runtime, benchmark)
│   ├── __init__.py
│   ├── types.py             # ContextHandle, RecallBenchmarkResult
│   ├── context.py           # externalize_context() — 100K+ token → symbolic handles
│   ├── runtime.py           # RLMRuntime — restricted peek/llm_batch primitives
│   ├── prototype.py         # RLMPrototype — gratitude-loop detection + recall benchmark
│   └── fixtures.py          # StandardRecallBaseline for lost-in-the-middle testing
├── stores/
│   ├── __init__.py
│   ├── base.py              # Abstract TrustStore protocol (get/put/delete/all_pairs)
│   ├── memory.py            # In-memory dict store (default)
│   ├── file.py              # JSON file-backed store (cross-session persistence)
│   └── fulcrum.py           # FulcrumStore — write-through to Fulcrum IO API (REST deferred, Redis IPC is canonical)
└── adapters/
    ├── __init__.py
    └── langgraph.py         # TrustAwareGraph wrapper for LangGraph StateGraph
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
- Store interface is abstract — MemoryStore (default), FileStore (persistent), FulcrumStore (write-through to IO)
- LangGraph adapter wraps StateGraph — zero changes to user's existing graph code
- All state mutations go through TrustManager — single source of truth
- IPC bridge writes circuit state to Redis (`agent:{id}:circuit_state` → int 0-3) for O(1) Go-side reads
- `terminate()` is an administrative kill switch — bypasses trust math, pair cannot recover without explicit reset
- BackgroundFlusher batches store writes on a background thread to avoid blocking agent execution
- ContextVar isolation prevents concurrent graph evaluations from contaminating each other

## Cross-Repo Parity
- Go evaluator (`fulcrum-io/internal/trust/`) must produce identical results to Python evaluator
- Parity enforced via shared fixtures: `fulcrum-io/tests/parity/trust_parity_fixtures.json`
- Redis key schema and CircuitState values (0-3) are the IPC contract between Python and Go
- FulcrumStore REST path (`/api/trust/events`) is deferred — Redis IPC bridge is the canonical integration

## Quality Gates
- 95%+ coverage on core (types, evaluator, manager, decay, stores)
- 90%+ coverage on adapters
- Zero mypy errors in strict mode
- All public APIs have docstrings + type hints
- No dependencies beyond numpy (optional) for core
