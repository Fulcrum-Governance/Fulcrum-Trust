# fulcrum-trust — Agent Context

**Last updated:** 2026-04-17

---

## Four-Repo Architecture

This is one of four repositories under the `Fulcrum-Governance` GitHub org.

| Repo | Local Path | Language | Purpose |
|------|-----------|----------|---------|
| **fulcrum-io** | `/Users/td/ConceptDev/Projects/Fulcrum` | Go 1.26.2 | Backend platform: gRPC server, REST gateway, MCP endpoint, policy engine, cognitive layer, foundry, entropy monitor |
| **governance-interception-layer** | `/Users/td/ConceptDev/Projects/governance-interception-layer` | Go 1.26.2 | Out-of-process enforcement boundary: transport adapters, shared governance pipeline, cross-transport parity |
| **fulcrum-trust** (this repo) | `/Users/td/ConceptDev/Projects/fulcrum-trust` | Python 3.9+ | Trust model authority: beta-distribution trust math, circuit breaker, LangGraph adapter, IPC bridge, RLM prototype |
| **Fulcrum-Proofs** | `/Users/td/ConceptDev/Projects/Fulcrum-Proofs` | Lean 4 / TLA+ / Python | Formal verification: Lean 4 proofs, TLA+ model checking, benchmark evidence, claim ledger |

### Cross-Repo Relationships
- **Trust parity**: Go trust implementation in `fulcrum-io` must match Python math here. Enforced via `make trust-parity-runtime` in the IO repo.
- **GIL boundary**: `governance-interception-layer` owns out-of-process transport interception; this repo owns trust math and adapters.
- **IPC bridge**: `fulcrum_trust/ipc/` communicates with `fulcrum-io` Go process via Redis-backed IPC (`internal/trust/` in Go).
- **Product bible**: Canonical product definition lives in `fulcrum-io/product/`. This repo's `PRODUCT.md` is a pointer file.

---

## Build & Test

```bash
pip install -e ".[dev]"     # Install with dev dependencies
pytest                       # Run all tests (186 tests, ~97% coverage)
pytest --cov=fulcrum_trust   # With coverage report
ruff check .                 # Lint
ruff format .                # Format
mypy fulcrum_trust/          # Type check
```

## Package Structure

```
fulcrum_trust/
├── evaluator.py      # Beta-distribution trust scoring
├── decay.py          # Exponential time-decay model
├── manager.py        # TrustManager — circuit breaker orchestrator
├── context.py        # ContextVar-based isolation for async
├── flusher.py        # BackgroundFlusher for batched store writes
├── types.py          # TrustState, TrustConfig, CircuitState enums
├── adapters/         # Framework adapters (LangGraph)
├── stores/           # MemoryStore, FileStore, FulcrumStore
├── ipc/              # Redis-backed IPC bridge
└── rlm/              # Recursive context engine prototype
```

## Publishing

- Package: `fulcrum-trust` on PyPI (current: v0.2.0)
- Build: `python -m build`
- Upload: `twine upload dist/*` (token: `PYPI_TRUST_TOKEN` in Doppler `fulcrum/prd`)
- Tag: `git tag vX.Y.Z && git push origin vX.Y.Z`

## Conventions

- Zero runtime dependencies (stdlib only, optional extras for IPC/adapters)
- Apache 2.0 license
- Conventional commits: `type(scope): message`
- Never commit secrets
