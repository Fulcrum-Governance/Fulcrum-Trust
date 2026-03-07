# ADR-010: Adopt Selected Engineering Patterns from Ecosystem Intelligence Audit

**Status:** Accepted
**Date:** March 5, 2026
**Decision Makers:** Tony Diefenbach (Founder)
**Applies To:** fulcrum-trust (D1), fulcrum-io (D2)

---

## Context

On March 5, 2026, an engineering intelligence audit was conducted across 10 open-source repositories in the AI agent governance ecosystem. The audit identified 11 adoptable patterns from external codebases. This ADR evaluates which patterns to adopt, defer, or reject — filtered against the current repo state and sprint timeline.

### Current Repo State

**fulcrum-trust** (Python, 47 commits, PyPI published, CI green)
- Core architecture complete: `TrustManager`, `TrustEvaluator`, `TrustStore` protocol, `MemoryStore`, `FileStore`, `FulcrumStore`
- Beta(α,β) evaluator with time-weighted exponential decay implemented
- Circuit breaker with CLOSED/OPEN/HALF_OPEN states implemented
- No LangGraph adapter yet (D1 priority gap)
- No async telemetry batching (events are synchronous)
- No ContextVar-based isolation for concurrent evaluations
- Package structure: `fulcrum_trust/` (flat layout)
- Apache 2.0 license

**fulcrum-io** (Go, 412 commits, 7 releases, CI green, 3 open issues, 1 open PR)
- Production-deployed on Railway (6 services)
- Core packages: `internal/brain/`, `internal/envelope/`, `internal/policyengine/`, `internal/mcpproxy/`, `internal/workflow/`, `internal/costengine/`
- Policy engine at 0.55ms P99 with Redis cache
- MCP proxy handles JSON-RPC interception
- No Secure MCP Server framework yet (D2 priority gap)
- No `/.well-known/mcp-servers` discovery endpoint
- No CEL policy expression support (current: deterministic JSON-based rules)
- BSL 1.1 license

**Fulcrum-Proofs** (Lean 4) — Not affected by this ADR.

### Sprint Constraints
- D1 ships March 17 (12 days from now)
- D2 ships March 31 (26 days from now)
- Solo founder, no team
- Every pattern adopted must directly serve a shipping deliverable

---

## Decision

### ADOPT NOW (D1 — fulcrum-trust, before March 17)

#### P-01: Thread-Safe Background Telemetry Batching
**Source:** Langfuse `langfuse/_client/resource_manager.py`
**Decision:** ADOPT — modified for scope

**Rationale:** fulcrum-trust currently processes events synchronously. When the LangGraph adapter runs trust evaluation on every node transition, synchronous event processing will block the agent's execution loop.

**Implementation scope for D1:**
- Add a `BackgroundFlusher` class to `fulcrum_trust/` that accepts trust events via a thread-safe `queue.Queue`
- Background thread batches events and flushes to the configured store at configurable intervals (default: 5 seconds or 100 events, whichever comes first)
- Graceful shutdown: flush remaining queue on `atexit` registration
- Do NOT port the full Langfuse `MediaUploadConsumer` architecture — we need queue + background thread + flush, not media handling.

**Estimated effort:** 1-2 days
**Files affected:** New `fulcrum_trust/flusher.py`, modify `fulcrum_trust/manager.py` to use it

#### P-03: ContextVar Execution Isolation
**Source:** Guardrails AI `guardrails/validator_base.py`
**Decision:** ADOPT

**Rationale:** When multiple LangGraph graphs run concurrently in the same process, trust evaluation state for Graph A must not leak into Graph B. Python's `contextvars.ContextVar` provides per-task isolation without locks.

**Implementation scope for D1:**
- Add `ContextVar` for current trust evaluation context in `fulcrum_trust/manager.py`
- Ensure `TrustManager` methods bind to the current context so concurrent `asyncio.create_task()` calls don't cross-contaminate

**Estimated effort:** 0.5-1 day
**Files affected:** `fulcrum_trust/manager.py`, new `fulcrum_trust/context.py`

#### P-02: Exception-Based Violation Pattern
**Source:** OpenAI Guardrails `GuardrailTripwireTriggered`
**Decision:** ADOPT — naming only

**Rationale:** fulcrum-trust needs a clean exception type for when the circuit breaker fires. A `TrustCircuitOpen` exception provides a cleaner integration point for the LangGraph adapter.

**Implementation scope for D1:**
- Add `TrustCircuitOpen(Exception)` to `fulcrum_trust/types.py`
- Add optional `raise_on_break=False` parameter to `TrustManager.evaluate()`
- LangGraph adapter uses `raise_on_break=True` by default

**Estimated effort:** 0.5 day
**Files affected:** `fulcrum_trust/types.py`, `fulcrum_trust/manager.py`

---

### ADOPT NOW (D2 — fulcrum-io, before March 31)

#### P-06: Durable Quarantine State
**Source:** Lasso MCP Gateway quarantine mechanism
**Decision:** ADOPT — adapted to existing circuit breaker

**Rationale:** Circuit breaker state is currently in-memory only. Persisting it to the trust store makes quarantine survive restarts.

**Implementation scope for D2:**
- Extend `TrustState` dataclass to include `circuit_state: CircuitBreakerState` field
- On circuit OPEN transition, persist to store immediately (bypass flusher)
- On startup, load stored states and restore circuit states

**Estimated effort:** 1 day
**Files affected:** `fulcrum_trust/types.py`, `fulcrum_trust/manager.py`, all store implementations

#### P-08: Well-Known MCP Discovery Endpoint
**Source:** MCP Gateway Registry `registry/api/wellknown_routes.py`
**Decision:** ADOPT

**Implementation:** Add `/.well-known/mcp-servers` HTTP endpoint to Secure MCP Server framework.
**Estimated effort:** 0.5 day
**Files affected:** New endpoint in `cmd/secure-mcp/` server framework

#### P-05: Governance Metadata via Headers (Simplified)
**Source:** agentgateway ExtAuthz header injection (PRs #818, #834)
**Decision:** ADOPT — simplified version

**Implementation:** Secure MCP Server proxy adds `X-Fulcrum-Trust-Score`, `X-Fulcrum-Policy-Result`, and `X-Fulcrum-Envelope-ID` headers to proxied requests. NOT the full ExtAuthz pattern.
**Estimated effort:** 1 day
**Files affected:** MCP proxy handler in `cmd/secure-mcp/` or `internal/mcpproxy/`

---

### DEFER (Post-Sprint)

- **P-04: CEL Policy Engine** — Significant architectural change. Spike during D3.
- **P-07: Safety-as-MCP-Peer** — Evaluate after D2 ships based on user feedback.
- **P-09: Stateful Simulation Testing** — LangWatch scenario framework for D3 empirical data.
- **P-10: Colang Runtime / Async Boundary** — Reference material for paper only.

### REJECT

- **P-11: MCP Gateway Landscape Gaps** — Positioning data, not code. Already in intel brief.

---

## Consequences

### Positive
- D1 ships with non-blocking telemetry, concurrent safety, and clean exception handling
- D2 ships with durable quarantine, discovery endpoint, and governance metadata headers
- Total adoption effort: ~5-6 days across both deliverables

### Risks
- P-01 (background flusher) introduces threading. Must test for race conditions.
- P-03 (ContextVar) may interact with LangGraph's own async context management.

---

# Claude Code Context Document

## Purpose
This document provides Claude Code with complete context to implement the patterns approved in ADR-010.

## Repository Locations
- **fulcrum-trust:** `/Users/td/ConceptDev/Projects/fulcrum-trust`
- **fulcrum-io:** `/Users/td/ConceptDev/Projects/Fulcrum`

## Implementation Order

### Phase A: fulcrum-trust D1 patterns (Days 1-3)

**Step 1: TrustCircuitOpen exception (P-02)**
- File: `fulcrum_trust/types.py`
- Add `class TrustCircuitOpen(Exception)` with attributes: `pair_id`, `trust_score`, `threshold`
- Add to `__init__.py` exports

**Step 2: ContextVar isolation (P-03)**
- New file: `fulcrum_trust/context.py`
- Define `_trust_context: ContextVar[Optional[TrustEvaluationContext]]`
- Modify `fulcrum_trust/manager.py`: wrap `evaluate()` to set/restore context
- Test: concurrent `asyncio.gather()` calls must not interfere

**Step 3: Background flusher (P-01)**
- New file: `fulcrum_trust/flusher.py`
- Class `BackgroundFlusher`: `queue.Queue` + `threading.Thread(daemon=True)` + `atexit` flush
- Modify `fulcrum_trust/manager.py`: add `async_flush: bool = False` parameter
- Maintain backward compatibility: `async_flush=False` preserves synchronous behavior

**Step 4: Update tests**
- `tests/test_types.py`, `tests/test_context.py`, `tests/test_flusher.py`, `tests/test_manager.py`
- Maintain 95%+ coverage target

**Step 5: Update documentation**
- `docs/api-reference.md`, `README.md`, `CHANGELOG.md`

### Phase B: fulcrum-io D2 patterns (Days 4-6)

**Step 6: Durable quarantine (P-06)** — persist circuit breaker state to stores
**Step 7: Well-known discovery endpoint (P-08)** — `GET /.well-known/mcp-servers`
**Step 8: Governance metadata headers (P-05)** — `X-Fulcrum-Trust-Score`, `X-Fulcrum-Policy-Result`, `X-Fulcrum-Envelope-ID`

## What NOT to Do
- Do NOT refactor existing store implementations beyond adding `circuit_state` field
- Do NOT add CEL support to the policy engine (deferred)
- Do NOT change the existing TrustManager API in any breaking way
- Do NOT add dependencies beyond Python stdlib for the flusher
- Do NOT implement the full Langfuse MediaUploadConsumer pattern
