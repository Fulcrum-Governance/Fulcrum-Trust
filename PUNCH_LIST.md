# fulcrum-trust — Punch List

Forward-looking / deferred work for `fulcrum-trust`. Captured 2026-06-22 when the
GSD planning tree and the ADR-010 implementation plan were archived (see
[`docs/_archive/2026-06-conductor-migration/`](docs/_archive/2026-06-conductor-migration/)).
The deferred-work content those documents carried — notably the plan's
"D2 Scope (Not In This Plan)" section, plus the `DEFERRED` notes in the README,
`CLAUDE.md`, and `FulcrumStore` — lives here now instead of being buried in the
archive.

**Status legend:** `ACTIONABLE` (doable in this repo now) · `CROSS-REPO`
(belongs to fulcrum-io) · `BLOCKED` (waiting on an external dependency) ·
`DECISION` (needs a call before any code).

> **Guardrail.** The trust-math / scoring core (`evaluator.py`, `decay.py`,
> `manager.py`, `types.py`) is complete, ≥95% covered, and Go-parity-tested. It
> has **no** deferred items, and **nothing in this list changes scoring
> semantics.** CEL policy support is *intentionally* deferred (ADR-010 §DEFER) —
> a decision, not a gap.

---

## Actionable in this repo

### PL-1 · Persist & restore `circuit_state` (P-06 D1→D2 handoff) · ACTIONABLE
`TrustState.circuit_state` was added as the D1 foundation (ADR-010 Wave 1) but the
persist/restore logic was explicitly left for D2 and never built.
- **Evidence:** archived adr-010 plan §"D2 Scope (Not In This Plan)"
  (`docs/_archive/2026-06-conductor-migration/adr-010-implementation-plan.md:593-601`),
  Constraint 5 (`:570`), `:530` ("Populated by D2 store persistence — not yet active in D1").
- **Scope:** persist `circuit_state` in `MemoryStore` / `FileStore` / `FulcrumStore`;
  restore it on `TrustManager` init. Additive with a default — existing serialized
  state stays valid.
- **Resolution:** dedicated Conductor lane. Persistence wiring + tests only; no
  scoring change. Refresh the Go parity fixtures if the serialized shape changes.

### PL-2 · Silent-failure audit of best-effort paths · ACTIONABLE
Best-effort integration paths swallow exceptions with bare `pass`.
- **Evidence:** `fulcrum_trust/ipc/redis_bridge.py:183,188,205`;
  `fulcrum_trust/flusher.py:66,88`; "best-effort … never raises"
  (`redis_bridge.py:60,112`).
- **Question:** is every swallow telemetry-only (correctness-safe), or can the
  canonical Redis `circuit_state` write fail silently and desync the Go side? A
  silent failure on the IPC-contract write is not telemetry.
- **Resolution:** review lane (good fit for a silent-failure-hunter pass). Outcome
  is either "confirmed safe + documented" or a targeted fix that surfaces/logs the
  correctness-critical write. Trust-math untouched.

### PL-3 · RLM prototype: stabilize or keep labeled-unstable · DECISION → ACTIONABLE
`fulcrum_trust/rlm/` ships as a "prototype (public, unstable) / Phase 5".
- **Evidence:** `README.md:86`, `docs/rlm-python-prototype.md:3`,
  `CHANGELOG.md:32-37`; coverage gaps at `rlm/prototype.py:213-216,220`.
- **Decision needed:** promote to a supported API, keep explicitly-unstable, or
  split into its own package.
- **Resolution:** decide first; if promoting, its own lane (API surface +
  stability contract + coverage).

### PL-4 · Coverage top-up on real gaps · ACTIONABLE
- **Evidence:** uncovered lines in `rlm/prototype.py`, `rlm/fixtures.py:66,83,88`,
  `stores/file.py:27-28` (per `pytest --cov`). NOT `stores/base.py` (Protocol
  stubs — expected).
- **Resolution:** small test-only lane; no behavior change.

---

## Cross-repo (tracked here, resolved in fulcrum-io)

ADR-010 D2/D3 patterns whose home is fulcrum-io, not this package — tracked here
only because the archived plan documented them. This repo consumes the contract
(Redis key schema + `CircuitState` 0-3); it does not implement these.

- **PL-5 · P-06 server-side durable quarantine** — the runtime half of PL-1.
- **PL-6 · P-08 well-known MCP discovery endpoint** — `GET /.well-known/mcp-servers`.
- **PL-7 · P-05 governance metadata headers** — `X-Fulcrum-Trust-Score`,
  `X-Fulcrum-Policy-Result`, `X-Fulcrum-Envelope-ID`.
- **PL-8 · D3 / evaluate items** — P-04 CEL policy engine (D3 spike), P-07
  Safety-as-MCP-peer (evaluate post-D2), P-09 stateful simulation testing (D3).
  Evidence: `docs/ADR-010-engineering-intel-adoption.md` §DEFER,
  `docs/fulcrum-engineering-intel-brief.md:11-19`.

**Resolution:** raise on the fulcrum-io backlog; out of scope for this package.

---

## Blocked on external dependency

### PL-9 · FulcrumStore REST `/api/trust/events` · BLOCKED
`FulcrumStore` is local-first + best-effort REST; the REST endpoint is deferred
because fulcrum-io does not expose it.
- **Evidence:** `fulcrum_trust/stores/fulcrum.py:20-26`, `README.md:64-70`,
  `CLAUDE.md:80`.
- **Unblock condition:** fulcrum-io ships `/api/trust/events`. Until then behavior
  is correct (local state authoritative; warning log on ship failure) and
  `RedisIPCBridge` is the canonical integration. No action in this repo.

---

## Resolution approach

1. **This change (doc-only):** land this punch list. No source / trust-math edits.
2. **One lane per actionable item** (respects one-lane-one-task). Suggested order:
   **PL-1** (highest value, self-contained, the documented D1→D2 handoff) →
   **PL-2** (robustness, quick) → **PL-4** (coverage) → **PL-3** (after the decision).
3. **Cross-repo (PL-5..8):** track on the fulcrum-io backlog.
4. **Blocked (PL-9):** revisit when fulcrum-io ships the endpoint.
