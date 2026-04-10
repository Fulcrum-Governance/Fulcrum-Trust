# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-04-09

### Added

- **IPC Bridge** (`fulcrum_trust/ipc/`): Cross-process trust state synchronization
  - `CircuitState` enum (TRUSTED=0, EVALUATING=1, ISOLATED=2, TERMINATED=3) matching Go-side constants
  - `IPCBridge` protocol for pluggable implementations
  - `RedisIPCBridge`: atomic Redis MULTI/EXEC writes + optional NATS telemetry
  - `NullBridge`: no-op for when IPC is not configured
  - Redis key schema: `agent:{id}:circuit_state` → integer (0-3)

- **RLM Prototype** (`fulcrum_trust/rlm/`): Governed long-context navigation
  - `externalize_context()` partitions 100K+ token histories into symbolic handles with a hard 128k token ceiling
  - `RLMRuntime` exposes restricted `peek` and `llm_batch` primitives for generated navigation programs
  - `RLMPrototype` detects planted gratitude-loop signatures hidden in the middle 80% of long sessions
  - `StandardRecallBaseline` provides a deterministic head-tail baseline for lost-in-the-middle benchmarking
  - Benchmark result: prototype recall `1.0` vs baseline `0.0` across five middle-position fixtures

- **FulcrumStore** (`fulcrum_trust/stores/fulcrum.py`): Write-through store that mirrors trust state locally and ships events to Fulcrum IO API with `X-API-Key` auth. REST path is deferred; Redis IPC bridge is the canonical integration.

- `TrustCircuitOpen` exception: raised when `raise_on_break=True` and trust drops below threshold after evaluation
- `BackgroundFlusher`: thread-safe background batching for trust state events, preventing synchronous store I/O from blocking agent execution
- `fulcrum_trust/context.py`: ContextVar-based execution isolation for concurrent evaluations
- `TrustManager(async_flush=True)`: opt-in async event persistence via BackgroundFlusher
- `TrustManager(ipc_bridge=...)`: opt-in IPC bridge for cross-process trust state sync
- `TrustManager.evaluate(raise_on_break=True)`: opt-in exception on circuit break
- `TrustManager.terminate()`: administrative kill switch — permanently terminates an agent pair, bypasses trust math
- `TrustState.circuit_state` field: tracks CLOSED/OPEN/HALF_OPEN/TERMINATED transitions
- Store parity tests: parametrized FulcrumStore vs MemoryStore validation
- 186 tests, 95.65% coverage

## [0.1.0] - 2026-02-19

### Added

- Beta distribution trust model (`TrustEvaluator`) with configurable alpha/beta priors
- `TrustManager` orchestrating evaluation, storage, and time-decay in a single interface
- Exponential decay toward uninformative prior (configurable half-life, default 24h)
- `MemoryStore` (default, in-process) and `FileStore` (JSON-backed, cross-session persistence)
- Abstract `TrustStore` Protocol for custom store implementations
- LangGraph adapter (`TrustAwareGraph`) wrapping existing `StateGraph` graphs with zero changes to graph code
- `TrustOutcome.PARTIAL` for fractional trust signals (weighted at 0.5 by default)
- Circuit breaker: `should_terminate()` returns `True` below configurable threshold (default 0.3)
- `TrustConfig` for threshold, half-life, and outcome weight configuration
- Three runnable demos: gratitude loop, drift detection, and recovery scenarios
- 97 tests, 96.83% coverage, mypy strict clean, zero runtime dependencies

[0.2.0]: https://github.com/Fulcrum-Governance/fulcrum-trust/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Fulcrum-Governance/fulcrum-trust/releases/tag/v0.1.0
