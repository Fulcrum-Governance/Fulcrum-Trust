# fulcrum-trust

**Trust-based circuit breaking for multi-agent AI systems.**

Prevent infinite loops, coordination drift, and runaway costs in multi-agent workflows using formally validated trust degradation.

## The Problem

Multi-agent AI systems fail 41-87% of the time in production. The canonical example: two AutoGen agents entered a gratitude loop that ran for 11 days and cost $47,000 — because neither agent could recognize the interaction had become unproductive.

Loop counters and timeouts are static. They terminate after N iterations regardless of whether the interaction is productive. **fulcrum-trust** is adaptive — it tracks coordination quality and terminates only when trust degrades below a configurable threshold.

## Quick Start

```bash
pip install fulcrum-trust
```

```python
from fulcrum_trust import TrustManager, TrustOutcome

tm = TrustManager(threshold=0.3)

# Record interaction outcomes
state = tm.evaluate("agent-a", "agent-b", TrustOutcome.SUCCESS)
print(f"Trust: {state.trust_score:.3f}")  # 0.667

state = tm.evaluate("agent-a", "agent-b", TrustOutcome.FAILURE)
print(f"Trust: {state.trust_score:.3f}")  # 0.500

# Check if agents should stop collaborating
should_stop = tm.should_terminate("agent-a", "agent-b")
```

### LangGraph Integration

```python
from fulcrum_trust import TrustManager
from fulcrum_trust.adapters.langgraph import TrustAwareGraph
from langgraph.graph import StateGraph

graph = StateGraph(MyState)
# ... define your nodes and edges ...

# Wrap with trust-based circuit breaking
trusted_graph = TrustAwareGraph(graph, trust_manager=TrustManager())
result = trusted_graph.invoke(initial_state)
# Automatically terminates if agent coordination degrades
```

## How It Works

fulcrum-trust uses a **Beta distribution trust model** with formal termination guarantees:

```
Trust(t) = (α + 1) / (α + β + 2)
```

- New agent pairs start at 0.5 (uninformative prior)
- Successful interactions increase trust
- Failed/unproductive interactions decrease trust
- When trust drops below threshold → terminate
- Optional time decay ensures stale relationships degrade

The termination bound is provably finite — not a heuristic, a mathematical guarantee.

## Examples

```bash
# See trust-based termination prevent the $47K gratitude loop
python examples/gratitude_loop.py --with-trust

# Compare: without trust, the loop runs indefinitely
python examples/gratitude_loop.py --without-trust --max-iterations=50
```

## Documentation

- [API Reference](docs/api-reference.md)
- [Trust Model Mathematics](docs/trust-model.md)
- [LangGraph Integration Guide](docs/langgraph-guide.md)

## Part of the Fulcrum Ecosystem

fulcrum-trust is the open-source trust engine from [Fulcrum](https://fulcrumlayer.io) — the Agentic Operating System providing governance and coordination for multi-agent AI. The trust module works standalone with zero dependencies, or connects to the Fulcrum platform for centralized trust management, dashboards, and enterprise governance.

## License

Apache 2.0
