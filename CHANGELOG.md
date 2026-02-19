# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
