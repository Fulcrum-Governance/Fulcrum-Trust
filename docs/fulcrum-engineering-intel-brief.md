# Engineering Intelligence Brief — Extracted Patterns for Fulcrum AOS Sprint
**Source:** Gemini Deep Research Audit v3 (March 5, 2026)
**Extracted:** March 5, 2026 — External-repo findings only, all sources verified

---

## Priority Adoption Queue

| ID | Pattern | Source | Sprint | Effort | Impact |
|---|---|---|---|---|---|
| P-01 | Thread-safe background batching | Langfuse | D1 | 2-3 days | High |
| P-03 | ContextVar execution isolation | Guardrails AI | D1 | 1-2 days | High |
| P-02 | Exception-based violation handling | OpenAI Guardrails | D1 | 1 day | Medium |
| P-06 | Durable quarantine state | Lasso Gateway | D2 | 1-2 days | High |
| P-08 | Well-known discovery endpoint | MCP Registry | D2 | 1 day | Medium |
| P-05 | ExtAuthz header injection for MCP | agentgateway | D2 | 3-5 days | High |
| P-07 | Safety-as-MCP-peer (evaluate) | Superagent | D2 | 0 days | Decision |
| P-09 | Stateful simulation testing | LangWatch | D3 | 3-5 days | High |
| P-04 | CEL policy engine (evaluate only) | agentgateway | Post | 2 days | Future |
| P-10 | Async boundary handling | NeMo | D3 | 1 day | Medium |

---

## D1 Patterns (shipping March 17)

### P-01: Thread-Safe Background Telemetry Batching
**Source:** Langfuse `langfuse/_client/resource_manager.py`
**URL:** https://github.com/langfuse/langfuse-python/blob/main/langfuse/_client/resource_manager.py
**Verified:** ✅ Singleton with `threading.RLock()`, `MediaUploadConsumer` worker, `Queue`-based batching, `.pause()`/`.join()` shutdown.
**Adopt:** Queue + background thread + atexit flush for fulcrum-trust telemetry. NOT full MediaUploadConsumer.

### P-02: Exception-Based Violation Pattern
**Source:** OpenAI Guardrails `GuardrailTripwireTriggered`
**URL:** https://github.com/openai/openai-guardrails-python
**Verified:** ✅ `GuardrailsOpenAI`/`GuardrailsAsyncOpenAI` classes, `GuardrailTripwireTriggered` exception.
**Adopt:** `TrustCircuitOpen(Exception)` with `raise_on_break=True` for LangGraph adapter.

### P-03: ContextVar Execution Isolation
**Source:** Guardrails AI `guardrails/validator_base.py`
**URL:** https://github.com/guardrails-ai/guardrails/blob/main/guardrails/validator_base.py
**Verified:** ✅ Imports `from contextvars import Context, ContextVar`, uses `PassResult`/`FailResult`/`ValidationResult`. Note: file scheduled for removal in 0.6.x.
**Adopt:** `ContextVar` for trust evaluation context isolation in concurrent LangGraph graphs.

## D2 Patterns (shipping March 31)

### P-05: MCP Session Persistence via ExtAuthz Headers
**Source:** agentgateway PRs #818, #834
**URL:** https://github.com/agentgateway/agentgateway
**Verified:** ✅ Crate structure confirmed, `crate::http::ext_authz::ExtAuthz` in `httpproxy.rs`, CEL 5-500x speedup.
**Adopt:** Inject `X-Fulcrum-Trust-Score`, `X-Fulcrum-Policy-Result`, `X-Fulcrum-Envelope-ID` headers.

### P-06: Dynamic Quarantine via Config Injection
**Source:** Lasso MCP Gateway
**URL:** https://github.com/lasso-security/mcp-gateway
**Verified:** ✅ Plugin-based quarantine, writes blocked status to config.
**Adopt:** Persist OPEN circuit breaker state to trust store. Survives restarts.

### P-08: Well-Known MCP Discovery Endpoint
**Source:** MCP Gateway Registry `registry/api/wellknown_routes.py`
**URL:** https://github.com/agentic-community/mcp-gateway-registry (Issue #119)
**Verified:** ✅ `/.well-known/mcp-servers` returning JSON payload with semantic search.
**Adopt:** Add discovery endpoint to Secure MCP Server framework.

## D3 Patterns (shipping May 11)

### P-09: Stateful Agent Simulation with Judge Pattern
**Source:** LangWatch `python/examples/test_testing_remote_agents_stateful.py`
**URL:** https://github.com/langwatch/scenario/blob/main/python/examples/test_testing_remote_agents_stateful.py
**Verified:** ✅ `StatefulAgentAdapter(scenario.AgentAdapter)`, `UserSimulatorAgent`, `JudgeAgent`, pytest integration. Also has Go SDK.
**Adopt:** Build simulation scenarios for trust model calibration (gratitude loop, drift, recovery). Produces empirical data for paper.

### P-10: Colang Runtime for Async Boundary
**Source:** NeMo Guardrails `nemoguardrails/rails/llm/llmrails.py`
**URL:** https://github.com/NVIDIA/NeMo-Guardrails/blob/develop/nemoguardrails/rails/llm/llmrails.py
**Verified:** ✅ Uses `nest_asyncio.apply()` for sync-in-async policy checks.
**Adopt:** Study only — do NOT use `nest_asyncio`. fulcrum-trust should be natively async. Reference in paper.
