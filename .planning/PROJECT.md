# fulcrum-trust — Trust-Based Circuit Breaking for Multi-Agent AI

## What This Is

A pure Python package implementing trust-based circuit breaking for multi-agent AI systems. Uses Beta(α,β) distribution to mathematically model trust between agent pairs, with exponential time decay and a configurable circuit-breaker threshold (default 0.3). When trust degrades below threshold, the circuit opens and terminates the interaction — preventing runaway coordination failures like the $47K AutoGen gratitude loop incident.

## Vision

A lightweight Python package that brings formally validated trust mechanics to multi-agent systems. When Agent A asks Agent B to do something and it goes wrong, fulcrum-trust detects the degradation pattern and breaks the circuit before catastrophic cost accumulation — like the $47K AutoGen incident where agents entered a "gratitude loop" with no termination signal.

## Core Value

**Prevent runaway agent coordination failures** through mathematically grounded trust degradation with formal termination guarantees.

## Requirements

### Validated

(None yet — ship to validate)

### Active

**Core Engine**
- [ ] TRUST-01: Beta-distribution trust evaluator with configurable α/β priors
- [ ] TRUST-02: Bayesian trust updates from interaction outcomes (success/failure/partial)
- [ ] TRUST-03: Configurable trust threshold (default 0.3) triggering circuit break
- [ ] TRUST-04: Time-decay on trust scores (recent interactions weighted higher)
- [ ] TRUST-05: Relationship memory store (persistent agent-pair history)
- [ ] TRUST-06: In-memory and file-backed storage implementations

**LangGraph Adapter**
- [ ] LANG-01: TrustAwareGraph wrapper that injects trust evaluation at node boundaries
- [ ] LANG-02: Automatic outcome classification from LangGraph node results
- [ ] LANG-03: Trust-based conditional edges (route to recovery when trust degrades)
- [ ] LANG-04: Callback hooks for trust state changes

**Demos**
- [ ] DEMO-01: Gratitude loop reproduction ($47K incident) with trust-based termination
- [ ] DEMO-02: Drift detection — slow trust degradation over 100+ interactions
- [ ] DEMO-03: Recovery — trust rebuilding after circuit break + intervention

**Distribution**
- [ ] DIST-01: PyPI package (pip install fulcrum-trust)
- [ ] DIST-02: Comprehensive README with quickstart
- [ ] DIST-03: API reference documentation
- [ ] DIST-04: Blog post explaining the math + the problem
- [ ] DIST-05: Community distribution (HN, Reddit r/LocalLLaMA, AI Discord servers)

### Out of Scope

- Go implementation (lives in fulcrum-io monorepo at internal/trust/)
- MCP integration (Phase 2 deliverable)
- Cloud service / API (this is a local library)
- AutoGen/CrewAI adapters (post-launch, community-driven)
- UI/dashboard (not needed for a library)

## Constraints

- Pure Python, zero heavy dependencies (numpy/scipy OK, no torch/tensorflow)
- Python 3.9+ compatibility
- Apache 2.0 license (max adoption)
- Must work standalone — no Fulcrum platform dependency
- 95%+ test coverage on core, 90%+ on adapters
- 4-week delivery window (Weeks 1-4 of AOS sprint)

## Target Users

Python developers building multi-agent systems with:
- LangGraph (primary adapter target)
- AutoGen (future adapter)
- CrewAI (future adapter)
- Custom agent orchestration frameworks

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Separate repo from Fulcrum monorepo | Max OSS visibility, independent stars/issues/releases | github.com/Fulcrum-Governance/fulcrum-trust |
| Pure Python, no Go dependency | Zero friction adoption for Python ML community | pip install, no compilation |
| Beta distribution over ELO/simple decay | Formally validated with convergence proofs, captures uncertainty | Mathematically grounded moat |
| LangGraph adapter first | Largest growing framework, cleanest integration points | StateGraph wrapper pattern |
| Apache 2.0 license | Maximum adoption, no license friction | Standard OSS |

## Mathematical Foundation

Trust score: `T(α,β) = α / (α + β)` where α = successful interactions, β = failed interactions.

Properties:
- Starts uncertain: `Beta(1,1)` = uniform prior (trust = 0.5)
- Converges with evidence: more interactions → tighter distribution
- Circuit break threshold: `T < 0.3` (configurable)
- Time decay: exponential weighting on recent interactions
- Formal termination guarantee: after sufficient negative evidence, trust provably drops below threshold in bounded time

Full spec: `fulcrum-io/.claude/aos/research/TRUST_MODEL_SPEC.md`

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.9+ |
| Math | numpy (optional, pure Python fallback) |
| Testing | pytest, pytest-cov, pytest-asyncio |
| Typing | Full type hints, mypy strict |
| Packaging | pyproject.toml, setuptools |
| Docs | mkdocs-material |
| CI | GitHub Actions |

## Reference Documents

- `.claude/discovery.md` — Problem definition and competitive landscape
- `.claude/research.md` — MAST taxonomy, framework gaps, Beta math, LangGraph integration
- `.claude/plan.md` — 4-phase implementation plan (Week 1-4)
- `.claude/progress.md` — Task-level execution tracker
- `fulcrum-io/.claude/aos/research/TRUST_MODEL_SPEC.md` — Formal trust model spec
- `fulcrum-io/.claude/aos/phases/PHASE_1_TRUST_CIRCUIT_BREAKER.md` — Full phase spec

---
*Last updated: 2026-02-17 after project initialization*
