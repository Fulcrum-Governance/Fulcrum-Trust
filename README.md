# fulcrum-trust

The trust engine of the Fulcrum governance kernel. Trust-based circuit breaking for multi-agent AI systems.

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
        base_url="https://api.fulcrumlayer.io",  # best-effort REST event target
    )
)

tm.evaluate("orchestrator", "code-agent", TrustOutcome.SUCCESS)
```

> **Note:** The `/api/trust/events` REST endpoint is currently **DEFERRED** —
> fulcrum-io does not yet expose it. `FulcrumStore` writes locally first and
> best-effort ships events with a warning log on failure, so the agent keeps
> running and local trust state remains correct. For production cross-process
> integration today, use `RedisIPCBridge` (`fulcrum_trust.ipc.redis_bridge`),
> which writes circuit state to Redis for O(1) reads by the Go Execution
> Envelope.

## Install

```bash
pip install fulcrum-trust

# Optional numpy fast path for decay math:
pip install "fulcrum-trust[numpy]"
```

## Documentation

- [API Reference](docs/api-reference.md) — all public classes and methods
- [Blog post](docs/blog-trust-circuit-breaker.md) — why agents need circuit breakers
- [RLM Python Prototype](docs/rlm-python-prototype.md) — Phase 5 prototype benchmark and architecture (public, unstable)

## Support

- Email: [agent@fulcrumlayer.io](mailto:agent@fulcrumlayer.io)
- GitHub Discussions: [Fulcrum-Governance/fulcrum-trust/discussions](https://github.com/Fulcrum-Governance/fulcrum-trust/discussions)

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

## Part of the Fulcrum Architecture

`fulcrum-trust` is one of four repositories that make up the Fulcrum governance kernel — a portable, typed, pre-execution control plane that sits between intent and action:

| Repo | Role | License |
|------|------|---------|
| **[fulcrum-io](https://github.com/Fulcrum-Governance/fulcrum-io)** | Runtime control plane: gRPC/REST, MCP proxy, CLI, dashboard, SDKs | BSL 1.1 |
| **[governance-interception-layer](https://github.com/Fulcrum-Governance/governance-interception-layer)** | Out-of-process enforcement boundary: transport adapters, 4-stage pipeline | Apache 2.0 |
| **fulcrum-trust** (this repo) | Trust engine: Beta(α,β) evaluator, circuit breaker, LangGraph adapter | Apache 2.0 |
| **[Fulcrum-Proofs](https://github.com/Fulcrum-Governance/Fulcrum-Proofs)** | Formal core: Lean 4 proofs, claim ledger, evidence artifacts | MIT |

Project docs: [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [Changelog](CHANGELOG.md) · [Code of Conduct](CODE_OF_CONDUCT.md) · [Citation](CITATION.cff)

`FulcrumStore` bridges this package to the main Fulcrum backend with local-first persistence and best-effort REST event shipping. For production cross-process integration today, use `RedisIPCBridge`, which publishes circuit state for O(1) reads by the Go Execution Envelope. The Go backend has parity tests ensuring its trust implementation matches this Python package's behavior exactly.

See [ADR-003](https://github.com/Fulcrum-Governance/fulcrum-io/blob/main/product/ADRs/003-three-repo-architecture.md) for the original repo-architecture rationale; the `governance-interception-layer` repo was added in April 2026 when GIL shipped as the out-of-process enforcement boundary.

## Architecture

```
fulcrum_trust/
├── types.py        — TrustOutcome enum, TrustState, TrustConfig, TrustCircuitOpen
├── evaluator.py    — TrustEvaluator: Beta(α,β) scoring, pair_id generation
├── decay.py        — Exponential decay toward uninformative prior
├── manager.py      — TrustManager: orchestrates evaluator + store + decay
├── context.py      — ContextVar isolation for concurrent evaluations
├── flusher.py      — Background telemetry batching (non-blocking store writes)
├── rlm/
│   ├── context.py  — 128k-bounded long-context externalization into symbolic handles
│   ├── runtime.py  — Restricted `peek` + `llm_batch` navigation runtime
│   ├── prototype.py — Gratitude-loop analysis + lost-in-the-middle benchmark
│   └── fixtures.py — Deterministic 100K+ token synthetic session generator
└── stores/
    ├── base.py     — TrustStore Protocol (structural subtyping)
    ├── memory.py   — MemoryStore (default, in-process)
    ├── file.py     — FileStore (JSON-backed, cross-session)
    └── fulcrum.py  — FulcrumStore (local-first + backend event shipping)
```

## License

Apache 2.0. See [LICENSE](LICENSE).
