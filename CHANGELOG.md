# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `fulcrum_trust.rlm`: Phase 5 RLM Python prototype for governed long-context navigation
  - `externalize_context()` partitions 100K+ token histories into symbolic handles with a hard 128k token ceiling
  - `RLMRuntime` exposes restricted `peek` and `llm_batch` primitives for generated navigation programs
  - `RLMPrototype` detects planted gratitude-loop signatures hidden in the middle 80% of long sessions and emits a read → analyze → report trace
  - `StandardRecallBaseline` provides a deterministic head-tail baseline for lost-in-the-middle benchmarking
  - benchmark result: prototype recall `1.0` vs baseline `0.0` across five middle-position fixtures

- `TrustCircuitOpen` exception: raised when `raise_on_break=True` and trust
  drops below threshold after an evaluation (P-02, ADR-010)
- `BackgroundFlusher`: thread-safe background batching for trust state events,
  preventing synchronous store I/O from blocking agent execution (P-01, ADR-010)
- `fulcrum_trust/context.py`: ContextVar-based execution isolation for concurrent
  evaluations — Graph A trust state cannot contaminate Graph B (P-03, ADR-010)
- `TrustManager(async_flush=True)`: opt-in async event persistence via BackgroundFlusher
- `TrustManager.evaluate(raise_on_break=True)`: opt-in exception on circuit break
- `TrustState.circuit_state` field (foundation for D2 durable quarantine)

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

[Unreleased]: https://github.com/Fulcrum-Governance/fulcrum-trust/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Fulcrum-Governance/fulcrum-trust/releases/tag/v0.1.0
