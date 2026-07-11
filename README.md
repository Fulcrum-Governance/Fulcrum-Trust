# fulcrum-trust

Adaptive trust governance for the agent control plane. Bayesian Beta(α,β) trust evaluation, circuit breaking, and trust-aware routing for AI agent harnesses.

[![CI](https://github.com/Fulcrum-Governance/fulcrum-trust/actions/workflows/ci.yml/badge.svg)](https://github.com/Fulcrum-Governance/fulcrum-trust/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/fulcrum-trust)](https://pypi.org/project/fulcrum-trust/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)

## What is this?

`fulcrum-trust` implements a Beta distribution trust model for agent-to-agent relationships. When an agent pair's trust score drops below a configurable threshold, the circuit breaks — terminating the interaction before runaway loops occur.

The math: every interaction updates a `Beta(α, β)` distribution. Trust score = `α / (α + β)`. Starting at `(1.0, 1.0)` gives an uninformative prior of 0.5. Scores decay exponentially toward 0.5 over time (stale relationships revert to uncertainty).

### Bounded detection latency (`alpha_max`)

By default `α` grows without bound, so a pair with a long clean history buys a
proportionally long runway of tolerated failures before the circuit opens.
Setting `TrustConfig(alpha_max=K)` clamps `α` at `K` after every update,
converting that runway into a constant: with threshold `θ = p/q`, the circuit
opens within `ceil(α_max·(q−p)/p)` consecutive failures regardless of prior
history (raw model; θ = 0.3 ⇒ `ceil(α_max·7/3)`, e.g. `α_max=20` ⇒ ≤ 47).

```python
from fulcrum_trust import TrustManager, TrustConfig

tm = TrustManager(config=TrustConfig(alpha_max=20.0))  # detection ≤ 47 failures
```

The knob is a tradeoff surface: smaller `α_max` → tighter detection bound but
coarser trust resolution. Pick per deployment — there is no hardcoded value,
and `alpha_max=None` (the default) preserves the original unbounded behavior
exactly. Validation requires `alpha_max >= alpha_prior > 0`;
`alpha_max == alpha_prior` is a legal boundary that freezes success accrual
entirely — degenerate in practice.

**Recovery under the cap.** Bounded detection has a flip side: once the
circuit opens with `β` well past the cap (`β > α_max·(q−p)/p`), successes
alone can never re-cross `θ` — the score is pinned at `α_max/(α_max+β)`
because `α` cannot grow. Recovery flows through time decay (both parameters
contract toward the uninformative prior, restoring recoverability within a
fraction of a half-life), an explicit `reset()`, or operator action. This
asymmetry is intrinsic to capping success evidence; pair the cap with
`recovery_cooldown_seconds` for a governed re-entry probe once decay lifts
the score back above threshold.

**Claims scope.** The engine knob is **Implemented** (tested in
`tests/test_evaluator.py::TestAlphaMaxCap`). The worst-case bound itself is
**Proved** only for the *discrete capped model* in Lean — D4 Theorem 3.9
(`capped_prior_strict_responsiveness`), published in ["A Bounded,
Machine-Checkable Governance Kernel for Trust-Gated Agent Execution"](https://doi.org/10.5281/zenodo.19900714)
(DOI 10.5281/zenodo.19900714), which proves threshold crossing within
`q·(α_max+1)` for the Laplace `(α+1)/(α+β+2)` estimator over `Nat`. The
deployed Python estimator is raw `α/(α+β)` over `float`; the two models agree
at the prior and diverge with counts, so their constants differ.

> **CORRESPONDENCE (carried verbatim from the sprint spec — mandatory).**
> The Lean witness `q·(α+1)` is *sufficient, not minimal*. The deployed Python
> raw estimator has a tighter minimal bound (`β > α(q−p)/p`). Document both
> constants and which model each belongs to. For θ=0.3 and α_max=20: Lean
> sufficient bound `q(α_max+1)=210`; raw-model minimal `≈47`. Do not present
> the Lean constant as the operational detection latency without this note.

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
- [Formal Validation](docs/formal-validation.md) — Lean 4 proof backing for the formal termination guarantee
- [Blog post](docs/blog-trust-circuit-breaker.md) — why agents need circuit breakers
- [RLM Python Prototype](docs/rlm-python-prototype.md) — Phase 5 prototype benchmark and architecture (public prototype — unstable API, not production-stable)

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
| **[Fulcrum-Boundary](https://github.com/Fulcrum-Governance/Fulcrum-Boundary)** | Out-of-process enforcement boundary: transport adapters, 4-stage pipeline | Apache 2.0 |
| **fulcrum-trust** (this repo) | Trust engine: Beta(α,β) evaluator, circuit breaker, LangGraph adapter | Apache 2.0 |
| **[Fulcrum-Proofs](https://github.com/Fulcrum-Governance/Fulcrum-Proofs)** | Formal core: Lean 4 proofs, claim ledger, evidence artifacts | MIT |

Project docs: [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [Changelog](CHANGELOG.md) · [Code of Conduct](CODE_OF_CONDUCT.md) · [Citation](CITATION.cff)

`FulcrumStore` bridges this package to the main Fulcrum backend with local-first persistence and best-effort REST event shipping. For production cross-process integration today, use `RedisIPCBridge`, which publishes circuit state for O(1) reads by the Go Execution Envelope. The Go backend has parity tests ensuring its trust implementation matches this Python package's behavior exactly.

See [ADR-003](https://github.com/Fulcrum-Governance/fulcrum-io/blob/main/product/ADRs/003-three-repo-architecture.md) for the original repo-architecture rationale; the out-of-process enforcement boundary was added in April 2026 as GIL and now lives in the `Fulcrum-Boundary` repo.

## Architecture

```
fulcrum_trust/
├── types.py        — TrustOutcome enum, TrustState, TrustConfig, TrustCircuitOpen
├── evaluator.py    — TrustEvaluator: Beta(α,β) scoring, pair_id generation
├── decay.py        — Exponential decay toward uninformative prior
├── manager.py      — TrustManager: orchestrates evaluator + store + decay
├── context.py      — ContextVar isolation for concurrent evaluations
├── flusher.py      — Background telemetry batching (non-blocking store writes)
├── rlm/             — Phase 5 prototype: public but unstable API, not production-stable
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
