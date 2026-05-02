---
title: "Why Your AI Agents Need a Circuit Breaker (and How to Build One)"
date: 2026-02-19
tags: [agents, reliability, python, langchain, langgraph]
status: published
---

# Why Your AI Agents Need a Circuit Breaker (and How to Build One)

> Industry reports of multi-agent runaway loops have surfaced incidents reaching tens of thousands of dollars in API costs, accumulating over days before detection. The pattern: two agents — say an analyzer and a verifier — get stuck in a mutual clarification loop with no stop conditions, no cost ceilings, and no shared memory. The agents are doing something. Just nothing useful.

## What Actually Happened

The pattern is deceptively simple. Agent A produces a response. Agent B receives it, processes it, and produces its own response — reasonable on its face, non-empty, no error codes. Agent A receives that response, does the same. Repeat.

Neither agent has a goal-completion signal. Neither agent has memory of previous rounds. Each one sees a fresh input each time and produces a fresh output. From the system's perspective, everything looks healthy. Logs are clean. Responses are non-null. Latencies are normal. The agents are working hard. They're just not working on anything that matters.

What makes this failure mode particularly painful is that the system is doing exactly what it was designed to do: route agent A's output to agent B, and agent B's output back to agent A. The loop is correct. The agents are correct. The problem is that nobody has defined what "done" looks like — and so the system keeps running, racking up tokens and API calls, until someone notices.

This is the gratitude loop failure mode. You can reproduce it in under 60 seconds:

```bash
pip install -e .
python examples/gratitude_loop.py --without-trust   # runs all 50 iterations — shows the problem
```

No matter how many iterations you allow, the loop never terminates on its own.

## Why Hard Stops Don't Work

The first instinct is to add a maximum iteration count. Stop after 10 exchanges. Or 20. Or 50. It feels safe.

The problem is that "task complexity" varies wildly. A document processing pipeline might legitimately require 40 agent interactions. A code review system might need 20 back-and-forth cycles between a code-reading agent and an issue-tracking agent before both converge on a fix. A research synthesis pipeline might run for hours.

A hard iteration ceiling treats all of these tasks the same. Set it too low and you break legitimate workloads. Set it too high and you're back to the runaway-loop problem — just capped at a slightly lower ceiling.

What you actually need is a way to ask: is this interaction making progress? Not "how many steps have occurred" but "are the steps moving the work forward?" That question requires looking at the quality of each exchange, not just counting them.

## Trust as a Signal

Trust, in this context, is a quality signal derived from interaction history. Not a timer. Not a counter. A score that asks: given everything we've seen from this agent pair, how likely are they to produce useful work on the next interaction?

The key intuition: imagine you've watched two agents work together five times and all five went well. Now imagine you've watched them work together nine times — five successes, four failures. Both pairs have the same number of successes. But you'd reasonably trust the first pair more. The ratio of good to bad interactions matters.

But there's a second, subtler point. Imagine pair A has 5 successes and 0 failures. Pair B has 100 successes and 0 failures. Same ratio — perfect — but very different confidence levels. Pair A might just have been lucky. Pair B has demonstrated reliability at scale. A naive success rate can't capture this distinction. You need a way to represent *uncertainty about the score*, not just the score itself.

Beta distribution does exactly this. Instead of tracking a single score, it tracks two parameters — alpha and beta — that represent accumulated evidence. High alpha, low beta: trustworthy and well-evidenced. Low alpha, low beta: new pair, uncertain. Equal alpha and beta: genuinely ambiguous. The distribution narrows as evidence accumulates, capturing both the score and your confidence in it.

## The Math (You Can Skip This)

The plain-English version first: think of `alpha` as a running tally of good interactions and `beta_val` as a running tally of bad ones. The trust score is simply:

```
T(alpha, beta_val) = alpha / (alpha + beta_val)
```

Start with `alpha=1.0` and `beta_val=1.0` — this is the uninformative prior. We have no evidence yet, so we assign equal weight to success and failure. The starting score is 0.5.

Every time agents interact successfully, `alpha` increases by `success_weight` (default 1.0). Every failure increases `beta_val` by `failure_weight` (default 1.0). As alpha climbs, the score moves toward 1.0. As beta_val climbs, it drops toward 0.0.

The Bayesian framing matters for one important reason: a naive rolling average treats all history equally, and forgets the past at the same rate. Ten good interactions followed by two bad ones produces the same average as two good interactions followed by ten bad ones — if you're only tracking the last twelve. Those situations are not equivalent. The Beta model accumulates evidence monotonically; past interactions retain their weight.

Partial credit: not every interaction is cleanly success or failure. Agents might produce a valid response that's marginally useful — not wrong, but not forward motion. `TrustOutcome.PARTIAL` covers this case. It contributes fractionally to both alpha and beta, controlled by `partial_alpha_weight` and `partial_beta_weight` (both default to 0.5). In the gratitude loop case, we use `partial_alpha_weight=0.2, partial_beta_weight=0.8`: each "thank you" interaction adds 0.2 to alpha but 0.8 to beta_val, so the score drops at a rate that reflects the low productivity of each exchange.

Circuit break: when trust drops below `threshold` (default 0.3), `should_terminate()` returns `True`. At that point, the loop has produced enough evidence of low quality that continuing is unjustified.

Trust also decays over time. A pair that was trustworthy last month gets a fresh start after a configurable half-life (default 24 hours). This prevents stale evidence from locking out agents that have been retrained or updated.

## Three Failure Modes, Three Demos

**The Gratitude Loop.** Two agents praise each other's outputs. Every response is syntactically valid, semantically coherent, and completely useless. With `partial_beta_weight=0.8`, each PARTIAL interaction degrades trust faster than it builds it. Trust drops below the 0.3 threshold within 12–15 iterations. Without a circuit breaker, the loop runs all 50 iterations — and in production, indefinitely.

```bash
pip install -e .
python examples/gratitude_loop.py --with-trust    # terminates in ~12 iterations
python examples/gratitude_loop.py --without-trust # runs all 50 iterations
```

**Gradual Drift.** An agent starts healthy — strong SUCCESS outcomes — but degrades 1.5% per iteration over 120 interactions. No single catastrophic failure. Each individual interaction looks almost normal. A hard iteration cap won't catch this; the agent is "working." But trust accumulates the evidence: after 20 strong successes build a solid alpha, the creeping FAILUREs after iteration 47 eat into it until the circuit opens around iteration 85. The loop terminates 35 iterations before the maximum — without any single threshold-crossing event.

```bash
python examples/drift_detection.py  # circuit breaks around iteration 70-80
```

**Recovery.** Trust drops (circuit opens), a human reviews the agent, `TrustManager.reset()` clears the pair's history, and the agent earns trust back through consistent performance. Three explicit phases: degradation, intervention, recovery. The reset returns the pair to the uninformative prior (score 0.500), and 15 subsequent successes rebuild it to 0.941.

```bash
python examples/recovery.py  # degradation -> intervention -> recovery
```

## Using It in Your Code

The minimal integration is five lines:

```python
from fulcrum_trust import TrustManager, TrustOutcome

mgr = TrustManager()

# After each agent interaction:
state = mgr.evaluate("orchestrator", "worker", TrustOutcome.PARTIAL)

if mgr.should_terminate("orchestrator", "worker"):
    raise RuntimeError("Trust degraded — terminating agent loop")
```

`evaluate()` records the outcome and returns an updated `TrustState`. `should_terminate()` checks whether the current score is below threshold. Both calls are idempotent with respect to state order — `("orchestrator", "worker")` and `("worker", "orchestrator")` refer to the same pair.

For tighter control over the threshold or partial outcome weighting, pass a `TrustConfig`:

```python
from fulcrum_trust import TrustManager, TrustConfig

mgr = TrustManager(
    config=TrustConfig(
        threshold=0.4,
        partial_beta_weight=0.8,
    )
)
```

A higher threshold catches degradation earlier. A higher `partial_beta_weight` makes PARTIAL outcomes count more heavily against trust — useful when "almost right" is still wrong for your domain.

For persistence across restarts — useful for long-running pipelines or services that restart overnight — swap in `FileStore`:

```python
from fulcrum_trust import TrustManager
from fulcrum_trust.stores.file import FileStore

mgr = TrustManager(store=FileStore("trust_state.json"))
```

Trust history survives process restarts. Pairs that were degraded before a restart are still degraded after. Pairs that were healthy remain healthy.

If you're already using LangGraph, the adapter wraps your existing graph without touching its internals:

```python
from fulcrum_trust.adapters.langgraph import TrustAwareGraph

trusted_graph = TrustAwareGraph(your_graph, trust_manager)
```

No changes to your graph's nodes or edges. The adapter intercepts transitions, records outcomes, and injects termination edges when trust drops below threshold.

The store interface is abstract. `MemoryStore` (the default) keeps everything in a Python dict — good for single-process experimentation. `FileStore` serializes to JSON. The same interface is designed to support Redis or SQL stores later; implementing a custom store is a matter of subclassing `TrustStore` and implementing `get`, `put`, and `delete`.

## What This Doesn't Solve

Four honest limitations worth naming before you ship this to production:

- **It doesn't fix bad agents. It detects them faster.** If your agents produce garbage, `fulcrum-trust` will tell you sooner. The remediation — improving the agents — is still yours to handle.

- **It requires an outcome signal.** You classify each interaction as `SUCCESS`, `PARTIAL`, or `FAILURE`. The library provides the math; you provide the signal. In some systems this is trivial (did the downstream task complete?). In others it's the hard part.

- **It doesn't prevent all runaway loops.** Agent pairs that consistently produce PARTIAL outcomes at the default `partial_alpha_weight=0.5, partial_beta_weight=0.5` hover near a trust score of 0.5 indefinitely — they never trigger the 0.3 threshold. Tune `partial_beta_weight` upward for domains where "almost right" should degrade trust faster than it builds it.

- **It's not a replacement for monitoring.** Circuit breaking is a last resort. You still want cost alerts, latency dashboards, and human-readable logs. `fulcrum-trust` gives you a principled stop condition; the rest of your observability stack catches everything else.

## Try It

```bash
pip install fulcrum-trust
```

Then run any of the three demos above. The source is at github.com/Fulcrum-Governance/fulcrum-trust — issues and pull requests welcome.

The `examples/gratitude_loop.py` demo is the clearest entry point: two minutes to see the failure mode reproduced (modeled on the runaway-loop pattern described above), and two more to see the circuit breaker terminate it. From there, `drift_detection.py` and `recovery.py` cover the subtler cases that show up in production systems.

If you run into a failure mode that the library doesn't handle, open an issue. The model is extensible — custom stores, custom outcome classifiers, and alternative trust priors are all supported through the existing interfaces.
