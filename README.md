# fulcrum-trust

Trust-based circuit breaking for multi-agent AI systems.

[![CI](https://github.com/Fulcrum-Governance/fulcrum-trust/actions/workflows/ci.yml/badge.svg)](https://github.com/Fulcrum-Governance/fulcrum-trust/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/fulcrum-trust)](https://pypi.org/project/fulcrum-trust/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)

## What is this?

`fulcrum-trust` implements a Beta distribution trust model for agent-to-agent relationships. When an agent pair's trust score drops below a configurable threshold, the circuit breaks — terminating the interaction before runaway loops occur.

The math: every interaction updates a `Beta(α, β)` distribution. Trust score = `α / (α + β)`. Starting at `(1.0, 1.0)` gives an uninformative prior of 0.5. Scores decay exponentially toward 0.5 over time (stale relationships revert to uncertainty).

## Quick Start

```python
from fulcrum_trust import TrustManager, TrustOutcome

# Default: in-memory store, threshold=0.3, 24-hour decay half-life
tm = TrustManager()

# Record interaction outcomes
tm.evaluate("orchestrator", "code-agent", TrustOutcome.SUCCESS)
tm.evaluate("orchestrator", "code-agent", TrustOutcome.SUCCESS)
tm.evaluate("orchestrator", "code-agent", TrustOutcome.FAILURE)

# Check trust
print(tm.get_trust_score("orchestrator", "code-agent"))  # 0.6

# Circuit break check — use this in your agent loop
if tm.should_terminate("orchestrator", "code-agent"):
    raise RuntimeError("Circuit open — trust degraded below threshold")
```

Persist across sessions with FileStore:

```python
from fulcrum_trust import TrustManager, TrustOutcome, TrustConfig
from fulcrum_trust.stores import FileStore

tm = TrustManager(
    store=FileStore("trust_state.json"),
    config=TrustConfig(threshold=0.3, half_life_seconds=3600),  # 1-hour decay
)
```

Send trust events to Fulcrum backend with `FulcrumStore`:

```python
from fulcrum_trust import FulcrumStore, TrustManager, TrustOutcome

tm = TrustManager(
    store=FulcrumStore(
        api_key="your-fulcrum-api-key",
        base_url="https://api.fulcrumlayer.io",  # or local dashboard URL
    )
)

tm.evaluate("orchestrator", "code-agent", TrustOutcome.SUCCESS)
```

`FulcrumStore` writes locally first and then best-effort ships events to `POST /api/trust/events`
using `X-API-Key`. If the network call fails, the agent keeps running and local trust state
remains available.

## Install

```bash
pip install fulcrum-trust

# Optional numpy fast path for decay math:
pip install "fulcrum-trust[numpy]"
```

## Documentation

- [API Reference](docs/api-reference.md) — all public classes and methods
- [Blog post](docs/blog-trust-circuit-breaker.md) — why agents need circuit breakers

## Support

- Email: [agent@fulcrumlayer.io](mailto:agent@fulcrumlayer.io)
- Discord: invite link pending final channel URL (tracked in Fulcrum SHIP-03)

## Development

```bash
git clone https://github.com/Fulcrum-Governance/fulcrum-trust
cd fulcrum-trust
pip install -e ".[dev]"
pytest              # Run tests (requires >=95% coverage)
mypy fulcrum_trust/ # Type check (strict mode)
ruff check .        # Lint
ruff format .       # Format
```

## Architecture

```
fulcrum_trust/
├── types.py        — TrustOutcome enum, TrustState, TrustConfig, TrustCircuitOpen
├── evaluator.py    — TrustEvaluator: Beta(α,β) scoring, pair_id generation
├── decay.py        — Exponential decay toward uninformative prior
├── manager.py      — TrustManager: orchestrates evaluator + store + decay
├── context.py      — ContextVar isolation for concurrent evaluations
├── flusher.py      — Background telemetry batching (non-blocking store writes)
└── stores/
    ├── base.py     — TrustStore Protocol (structural subtyping)
    ├── memory.py   — MemoryStore (default, in-process)
    ├── file.py     — FileStore (JSON-backed, cross-session)
    └── fulcrum.py  — FulcrumStore (local-first + backend event shipping)
```

## License

Apache 2.0. See [LICENSE](LICENSE).
