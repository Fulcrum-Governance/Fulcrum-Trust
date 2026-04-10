<!-- product-bible | version: 1.1.0 | last-updated: 2026-04-09 -->

# Product Definition

The canonical product bible for the Fulcrum project (spanning all three repos) lives in the Fulcrum main repository:

**[Fulcrum/product/INDEX.md](https://github.com/Fulcrum-Governance/fulcrum-io/blob/main/product/INDEX.md)**

## This repo's role

`fulcrum-trust` is the **trust model authority**. It owns:
- Beta distribution trust math (`fulcrum_trust/evaluator.py`)
- Exponential decay model (`fulcrum_trust/decay.py`)
- Trust circuit breaker logic (`fulcrum_trust/manager.py`)
- LangGraph adapter (`fulcrum_trust/adapters/langgraph.py`)
- Store abstractions: MemoryStore, FileStore, FulcrumStore (Redis IPC canonical, REST deferred)
- IPC bridge (`fulcrum_trust/ipc/`) — Redis-backed cross-process trust state sync
- RLM prototype (`fulcrum_trust/rlm/`) — Recursive context engine Python implementation

This package is independently installable (`pip install fulcrum-trust`) under Apache 2.0.
It does not require the Fulcrum backend to function.

## Relationship to Fulcrum

Trust parity is enforced via fixture-based semantic checks in the Fulcrum main repo (`make trust-parity-runtime`). Changes to trust math in this repo must pass parity tests before merging.

See [ADR-002](https://github.com/Fulcrum-Governance/fulcrum-io/blob/main/product/ADRs/002-pure-python-trust.md) and [ADR-003](https://github.com/Fulcrum-Governance/fulcrum-io/blob/main/product/ADRs/003-three-repo-architecture.md) for the rationale.
