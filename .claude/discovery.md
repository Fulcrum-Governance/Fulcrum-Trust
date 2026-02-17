# fulcrum-trust — Discovery Log
## Q&A Exchanges During Project Definition
**Created:** February 17, 2026

---

## Session 1: February 17, 2026 — AOS Pivot Decision

### Q: What problem does fulcrum-trust solve?
**A:** Multi-agent AI systems have zero persistent relationship state between agents. Every interaction starts from scratch. There's no mechanism for agents to build coordination history, develop trust based on outcomes, or detect when coordination is degrading. This leads to documented failure rates of 41-86.7% across production systems.

The canonical failure: the $47,000 AutoGen incident (Nov 2025). Two agents (Analyzer and Verifier) entered an infinite clarification loop for 11 days because neither could recognize unproductive interaction patterns.

### Q: Why not just use loop counters or timeouts?
**A:** Loop counters and timeouts are static. They terminate after N iterations or T seconds regardless of whether the interaction is productive. Trust-based termination is adaptive — it tracks the quality of interactions and terminates only when coordination degrades below a threshold. The RCP formal analysis proved trust-based termination dominates simpler alternatives for agent drift and delegation failures (comparative mechanism analysis).

### Q: Who is the target user?
**A:** Python developers building multi-agent systems with LangGraph, AutoGen, or CrewAI. The package must be pip-installable with zero configuration and no backend dependency. The optional Fulcrum backend connection is an upsell, not a requirement.

### Q: How does this relate to Fulcrum (the governance platform)?
**A:** fulcrum-trust is the open-source adoption driver for the broader AOS (Agentic Operating System) vision. It validates the trust model with real developers. The commercial Fulcrum platform adds governance, cost prediction, and enterprise features on top. Think Supabase model: open-source core drives adoption, hosted platform drives revenue.

### Q: Why a separate repo vs. Fulcrum monorepo?
**A:** Maximum open-source visibility. Independent star count. Feels like a community project, not a sales funnel. The Go trust module stays in Fulcrum monorepo (`internal/trust/`, `pkg/trust/`) for server-side performance. This Python package is the developer-facing interface.

### Q: What's the competitive landscape for this specific tool?
**A:** Nobody has shipped a trust-based circuit breaker for multi-agent systems. Fiddler AI ($100M) uses classification-based "Trust Models" (different concept — content safety scoring, not inter-agent relationship tracking). Guardrails AI does input/output validation. Langfuse/Helicone do retroactive observability. The trust-based coordination layer is genuinely unoccupied.

### Q: What are the formal mathematical foundations?
**A:** Beta distribution trust model validated through:
- **Game theory:** Nash equilibria proving bonded agent pairs converge to (Cooperate, Cooperate)
- **Markov chains:** Convergence proof to stable coordination states under ergodicity + aperiodicity + bounded rewards
- **State machines:** Bounded termination guarantee — max iterations provably finite
- **Comparative analysis:** Trust dominates for drift detection and delegation failures; fails for race conditions (which require synchronization primitives)

Full proofs in the "AI Relationship Layer" Claude Project and the RCP comprehensive briefing document.

### Q: What does the 90-day sprint timeline look like for this component?
**A:** Weeks 1-4 of the AOS sprint. Week 1: Go core + portable evaluator. Week 2: envelope integration + Python foundation. Week 3: LangGraph adapter + gratitude loop demo. Week 4: polish + PyPI publish + community distribution.

---

## Open Questions (To Resolve During Implementation)

1. **LangGraph version pinning:** Which LangGraph version to target? Need to check current stable.
2. **AutoGen adapter:** Include in v0.1.0 or defer? Recommendation: defer, focus on LangGraph.
3. **Async support:** Should TrustManager be async-first? LangGraph supports both sync and async.
4. **Visualization:** Include a simple trust score plot utility? (matplotlib optional dependency)
5. **Threshold auto-tuning:** Should the package suggest optimal thresholds based on interaction patterns? Defer to v0.2.0.

---

*Updated: February 17, 2026*
