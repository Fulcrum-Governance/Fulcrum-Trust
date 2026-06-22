# Phase 3: Demos + Content - Research

**Researched:** 2026-02-18
**Domain:** Python demo scripts, CLI argument patterns, terminal output, technical blog writing
**Confidence:** HIGH

---

## Summary

Phase 3 produces three standalone Python scripts in `examples/` and one blog post in `docs/`. The scripts must run without LLM API calls — they use plain Python functions as deterministic simulated agents. The existing `fulcrum_trust` library (Phases 1+2) provides the complete API surface; the demos are consumers, not builders. The gratitude loop reproduces a documented real-world pattern (two agents mutually reinforcing each other's outputs without stop conditions, accumulating $47K in API costs over 11 days). All three demos can be written using only the standard library plus `fulcrum_trust` — no additional runtime dependencies are required.

The core engineering challenge is making the simulated agents produce outputs that map correctly to `TrustOutcome` values (SUCCESS, FAILURE, PARTIAL) without triggering the `OutcomeClassifier`'s heuristics in unexpected ways. The demo loop logic must mirror the existing `TrustManager.evaluate()` / `TrustManager.should_terminate()` API exactly. Terminal output should use ANSI escape codes directly (no `rich` dependency) to show trust score progression clearly.

**Primary recommendation:** Write all three demos as self-contained scripts that call `TrustManager` directly (not `TrustAwareGraph`), drive `TrustOutcome` manually based on a deterministic simulation function, and print iteration-by-iteration trust scores with a clear termination summary.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DEMO-01 | Runnable gratitude loop example with and without trust | CLI argparse pattern + deterministic agent simulation + `TrustManager.evaluate()` / `should_terminate()` API |
| DEMO-02 | Runnable drift detection example — trust detects gradual quality degradation over 100+ interactions | `TrustOutcome.PARTIAL` sequences drive beta accumulation; simulate quality score dropping 1% per iteration |
| DEMO-03 | Runnable recovery example — trust drops, circuit breaks, agent recovers, trust rebuilds | `TrustManager.reset()` as intervention; show alpha/beta values and score across all three phases |
</phase_requirements>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `fulcrum_trust` | 0.1.0 (local) | Trust evaluation, circuit breaking | It IS the product being demonstrated |
| `argparse` | stdlib | `--with-trust` / `--without-trust` CLI flags | Standard library, no install required |
| `sys` | stdlib | Exit codes, argv | Standard library |
| `time` | stdlib | Iteration pacing (optional sleep for readability) | Standard library |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| ANSI codes (inline) | N/A | Colored terminal output (green=healthy, yellow=warning, red=terminated) | All three demos — no extra dep |
| `math` | stdlib | Computing trust score thresholds for display | Demo-02 drift calculation |
| `dataclasses` | stdlib | Simulation state structs | If demo state becomes complex |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Raw ANSI codes | `rich` library | `rich` is excellent but adds a dependency; demos must be zero-install beyond `fulcrum_trust` |
| Raw ANSI codes | `colorama` | Adds dependency; only needed for Windows compat which isn't required here |
| `argparse` | `sys.argv` direct | `argparse` provides `--help` for free and validates flags correctly |
| `TrustManager` direct | `TrustAwareGraph` | Direct is simpler for demos; `TrustAwareGraph` requires LangGraph installed |

**Installation:**
```bash
pip install -e .   # installs fulcrum_trust from source
# No additional packages needed for any demo
```

---

## Architecture Patterns

### Recommended Project Structure
```
examples/
├── gratitude_loop.py      # DEMO-01: --with-trust / --without-trust
├── drift_detection.py     # DEMO-02: 100+ iterations, gradual PARTIAL degradation
└── recovery.py            # DEMO-03: drop -> circuit break -> reset -> rebuild

docs/
└── blog-trust-circuit-breaker.md   # Blog post
```

### Pattern 1: Deterministic Agent Simulation Without LLMs

**What:** Replace LLM calls with Python functions that return predetermined outputs. For gratitude loop: agent A always returns the same string praising agent B's last output. For drift: response quality score decreases by a fixed amount per call.

**When to use:** All three demos. The `OutcomeClassifier` in `TrustAwareGraph` inspects state dicts, but since we're calling `TrustManager` directly, we control `TrustOutcome` ourselves — no classifier heuristics involved.

**Gratitude loop simulation:**
```python
# Source: project codebase analysis (fulcrum_trust/types.py)
# Agents echo praise back and forth. Outcome: always PARTIAL (not progressing, not failing)
_PRAISE = [
    "Thank you! That was incredibly helpful.",
    "Great point! I completely agree with your assessment.",
    "Excellent work! Your analysis is spot on.",
]

def agent_a(iteration: int, last_response: str) -> str:
    """Gratitude-echoing agent. Always returns praise, never advances task."""
    return _PRAISE[iteration % len(_PRAISE)]

def agent_b(iteration: int, last_response: str) -> str:
    """Mirror agent. Reflects praise back."""
    return _PRAISE[(iteration + 1) % len(_PRAISE)]
```

**Why PARTIAL not FAILURE:** Gratitude loop agents ARE responding (not None/empty), but they're not making progress. PARTIAL correctly models "something happened but not useful." This drives `beta_val` up slowly, eventually crossing the threshold.

### Pattern 2: Trust Score to Outcome Mapping (Drift Demo)

**What:** Map a simulated quality score (float 0.0–1.0, decreasing each iteration) to a `TrustOutcome`. Quality >= 0.7 → SUCCESS, 0.3–0.7 → PARTIAL, < 0.3 → FAILURE.

**When to use:** DEMO-02 drift detection.

```python
# Source: fulcrum_trust/types.py TrustOutcome enum analysis
def quality_to_outcome(quality: float) -> TrustOutcome:
    """Map a simulated quality score to a TrustOutcome."""
    if quality >= 0.7:
        return TrustOutcome.SUCCESS
    elif quality >= 0.3:
        return TrustOutcome.PARTIAL
    else:
        return TrustOutcome.FAILURE

def simulate_quality(iteration: int, base: float = 1.0, decay: float = 0.008) -> float:
    """Quality drops ~0.8% per iteration. Reaches PARTIAL zone around iteration 37."""
    return max(0.0, base - decay * iteration)
```

**Drift math:** Starting at 1.0, with 0.8% decay per iteration, quality reaches 0.7 (PARTIAL zone entry) at iteration ~37, reaches 0.3 (FAILURE zone) at iteration ~87. Over 100+ iterations, the trust system catches the degradation well before complete failure.

### Pattern 3: Recovery Arc (Three-Phase Demo)

**What:** Explicitly model three phases in one script: degradation (FAILURE outcomes) → circuit break → intervention (reset) → recovery (SUCCESS outcomes).

**When to use:** DEMO-03.

```python
# Source: fulcrum_trust/manager.py TrustManager.reset() analysis
def run_recovery_demo():
    mgr = TrustManager(config=TrustConfig(threshold=0.3))

    # Phase 1: Degradation — simulate bad agent outputs
    print_phase("DEGRADATION")
    for i in range(8):
        state = mgr.evaluate("orchestrator", "worker", TrustOutcome.FAILURE)
        print_trust_row(i, state, mgr.should_terminate("orchestrator", "worker"))
        if mgr.should_terminate("orchestrator", "worker"):
            print_circuit_break(state)
            break

    # Phase 2: Intervention — reset clears history, simulates human review
    print_phase("INTERVENTION")
    mgr.reset("orchestrator", "worker")
    print("  Trust history cleared. Agent reviewed and redeployed.")

    # Phase 3: Recovery — agent now performs well
    print_phase("RECOVERY")
    for i in range(15):
        state = mgr.evaluate("orchestrator", "worker", TrustOutcome.SUCCESS)
        print_trust_row(i, state, mgr.should_terminate("orchestrator", "worker"))
```

**Key insight on reset():** `TrustManager.reset()` deletes the trust state for the pair entirely (confirmed from `manager.py` line 105: `self._store.delete(pid)`). After reset, the next `evaluate()` call creates a fresh state with priors (alpha=1, beta=1, score=0.5). This is the natural "intervention" primitive.

### Pattern 4: CLI Flag Pattern (`--with-trust` / `--without-trust`)

**What:** Use `argparse` with `add_mutually_exclusive_group()` to require exactly one of `--with-trust` or `--without-trust`. Default to `--with-trust` (the interesting case) if neither provided.

**Python version note:** `argparse.BooleanOptionalAction` (Python 3.9+) creates `--foo` / `--no-foo` pairs but cannot produce `--with-trust` / `--without-trust` naming. Use explicit mutually exclusive group instead.

```python
# Source: https://docs.python.org/3/library/argparse.html
import argparse

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gratitude loop demo: shows trust-based termination vs. runaway loop"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--with-trust",
        action="store_true",
        default=False,
        help="Run with TrustManager enabled (circuit breaks within 15 iterations)",
    )
    group.add_argument(
        "--without-trust",
        action="store_true",
        default=False,
        help="Run without TrustManager (loop runs to MAX_ITERATIONS)",
    )
    args = parser.parse_args()
    # Default: show the protected version if no flag given
    if not args.with_trust and not args.without_trust:
        args.with_trust = True
    return args
```

**Important:** `--with-trust` becomes `args.with_trust` in the namespace (hyphens → underscores). Verify with `vars(args)` in tests.

### Pattern 5: Terminal Output Design

**What:** Print iteration-by-iteration trust scores with color coding. Use ANSI escape codes directly (no library dependency).

**Color scheme:**
- Green (`\033[32m`): trust > 0.5 — healthy
- Yellow (`\033[33m`): trust 0.3–0.5 — warning zone
- Red (`\033[31m`): trust < 0.3 — at or below threshold, circuit broken
- Bold (`\033[1m`): section headers and final verdict
- Reset (`\033[0m`): after every colored segment

```python
# Source: ANSI standard escape codes (no external reference needed)
GREEN  = "\033[32m"
YELLOW = "\033[33m"
RED    = "\033[31m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def trust_color(score: float) -> str:
    if score >= 0.5:
        return GREEN
    elif score >= 0.3:
        return YELLOW
    else:
        return RED

def print_trust_row(iteration: int, state: TrustState, terminated: bool) -> None:
    score = state.trust_score
    color = trust_color(score)
    status = f"{RED}CIRCUIT OPEN{RESET}" if terminated else f"{GREEN}OK{RESET}"
    print(
        f"  Iter {iteration:3d} | "
        f"Score: {color}{score:.3f}{RESET} "
        f"(α={state.alpha:.1f}, β={state.beta_val:.1f}) | "
        f"{status}"
    )
```

**Termination summary block:**
```python
def print_termination_summary(reason: str, iterations: int, final_score: float) -> None:
    print()
    print(f"{BOLD}{'='*55}{RESET}")
    print(f"{BOLD}  TERMINATED: {reason}{RESET}")
    print(f"  After {iterations} iterations")
    print(f"  Final trust score: {final_score:.3f}")
    print(f"{BOLD}{'='*55}{RESET}")
```

### Anti-Patterns to Avoid

- **Using `TrustAwareGraph` in demos:** Requires LangGraph installed; demos must be importable with just `fulcrum_trust`. Use `TrustManager` directly.
- **Non-deterministic agent behavior:** Random outputs make demo results unpredictable. Fix the simulation function precisely so the iteration count where circuit breaks is predictable and stated in `--help`.
- **Using `time.sleep()` by default:** Pacing is nice for live demos but annoying for CI. Add `--fast` flag or use sleep only when not in CI (`os.environ.get("CI")`).
- **Calling `should_terminate()` before `evaluate()`:** On a fresh pair, `should_terminate()` returns False even if score would be low. Always call `evaluate()` first to record the outcome.
- **Importing `TrustAwareGraph` at module level:** The `langgraph` optional dep may not be installed. The demos should only import from `fulcrum_trust` core (`TrustManager`, `TrustOutcome`, `TrustConfig`, `TrustState`).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Trust state accumulation | Custom success/failure counter | `TrustManager.evaluate()` | Beta conjugate prior already handles uncertainty correctly |
| Circuit break logic | `if failures > N: stop` | `TrustManager.should_terminate()` | Threshold already configurable; score is Bayesian, not naive count |
| Pair state storage | Dict keyed on (a, b) | `MemoryStore` (via TrustManager default) | Store already handles order-independent pair keys via SHA256 |
| Trust reset | Resetting a variable | `TrustManager.reset()` | Correctly deletes from store so next evaluate starts fresh with priors |
| Trust score calculation | `failures / (successes + failures)` | `state.trust_score` property | `alpha / (alpha + beta_val)` with proper Bayesian priors and decay |

**Key insight:** The demos are consumers of the library, not re-implementations. Every piece of trust logic already exists and is tested at 95%+ coverage. The demo scripts are thin wrappers that simulate agent behavior and visualize what the library does.

---

## Common Pitfalls

### Pitfall 1: Gratitude Loop Terminates Too Fast

**What goes wrong:** If failure_weight is high or threshold is high, trust drops below 0.3 in 2–3 iterations — not illustrative.
**Why it happens:** Default config has `threshold=0.3`, `failure_weight=1.0`, `partial_beta_weight=0.5`. With PARTIAL outcomes, beta grows at 0.5/iter from starting alpha=1, beta=1. Score = 1/(1+1)=0.5 at start. After k PARTIAL outcomes: alpha=1 + 0.5k, beta=1 + 0.5k, score still ≈ 0.5 indefinitely.
**Root cause:** PARTIAL adds equal weight to alpha and beta, so score stays near 0.5 forever with pure PARTIAL. Need to mix in FAILURE outcomes to drive score down, OR use a custom config with higher failure_weight for PARTIAL.
**Solution:** For DEMO-01, use a mix: first few iterations SUCCESS (trust builds), then PARTIAL (echoing), with occasional FAILURE (looping behavior classified as unproductive). OR use `partial_beta_weight=1.5` in a custom TrustConfig so PARTIAL outcomes drive score down. **Recommend the custom config approach** — it keeps simulation pure PARTIAL and terminates within ~10–12 iterations reliably.

**Math verification:** With `partial_alpha_weight=0.5, partial_beta_weight=1.5`, starting at alpha=1, beta=1:
- After 1 PARTIAL: alpha=1.5, beta=2.5, score=0.375
- After 2 PARTIAL: alpha=2.0, beta=4.0, score=0.333
- After 3 PARTIAL: alpha=2.5, beta=5.5, score=0.313
- After 4 PARTIAL: alpha=3.0, beta=7.0, score=0.300 — CIRCUIT BREAK
This gives termination within 4–5 iterations. Too fast. Use `partial_beta_weight=1.0` for ~10–12 iterations.

**Better approach:** Use `TrustConfig(partial_alpha_weight=0.2, partial_beta_weight=0.8)` — gratitude is mostly unproductive (more beta than alpha). Termination at ~12–14 iterations, matching the requirement of "within 15."

**Warning signs:** Run the demo and observe iteration count. If < 5 or > 20, adjust weights.

### Pitfall 2: Without-Trust Mode Must Actually Run All Iterations

**What goes wrong:** The `--without-trust` branch calls `should_terminate()` or accidentally creates a `TrustManager`. The demo must prove the problem, so it MUST run to `MAX_ITERATIONS` (suggest 50) without any trust check.
**Why it happens:** Copy-paste from the trust branch; or `TrustManager` imported but unused in a branch.
**How to avoid:** The `--without-trust` branch should have NO trust imports in its execution path. Use a simple `for i in range(MAX_ITERATIONS)` with no break condition.
**Warning signs:** `--without-trust` run ends before MAX_ITERATIONS.

### Pitfall 3: Drift Demo Doesn't Actually Trigger Termination

**What goes wrong:** Quality decays too slowly; after 100 iterations trust is still above threshold.
**Why it happens:** SUCCESS outcomes early in the run build up alpha substantially. With many early successes (iterations 0–36 at quality ≥ 0.7), alpha grows large. The subsequent PARTIAL/FAILURE outcomes must overcome that alpha accumulation.
**How to avoid:** Use 100 total iterations but design decay so FAILURE zone (quality < 0.3) is reached by iteration 87. The accumulated failures in iterations 88–100 must be enough to overcome the early successes. Verify by dry-running the math before writing the demo.

**Math check:** 36 SUCCESS → alpha=37, beta=1. Then 50 PARTIAL (0.5 each) → alpha=62, beta=26. Then 14 FAILURE → alpha=62, beta=40. Score = 62/102 = 0.608 — NOT terminated. Need steeper decay or higher initial failure weight for PARTIAL.

**Better design:** Use sharper threshold zones or a faster decay (1.2% per iteration instead of 0.8%). With 1.2% decay: PARTIAL zone at iteration 25, FAILURE zone at iteration 58. Then 42 FAILURE outcomes from iter 58–100 should overcome early successes of 25 iterations.

**Recommended parameters for drift demo:** `decay_per_iteration=0.012`, `TrustConfig(threshold=0.4)` — higher threshold catches degradation earlier and makes the demo more compelling. Termination expected around iteration 75–85.

### Pitfall 4: Recovery Demo Alpha/Beta Values Confuse Readers

**What goes wrong:** During recovery phase, trust score rebuilds but slowly, and readers don't understand why it's 0.4 after 5 SUCCESS outcomes.
**Why it happens:** After degradation phase, alpha and beta are both large (e.g., alpha=1, beta=12 after 11 FAILURE). Adding 5 SUCCESS outcomes gives alpha=6, beta=12, score=0.33 — still below threshold. Recovery takes many more successes than degradation.
**How to avoid:** Use `TrustManager.reset()` as the intervention between phases. After reset, next evaluate starts fresh (alpha=1+success_weight=2, beta=1, score=0.667 after first SUCCESS). This makes recovery immediately visible and teaches that reset is the intervention primitive.
**Warning signs:** Recovery phase shows trust stuck below threshold for many iterations with no visible trend.

### Pitfall 5: Blog Post Beta Math Loses Non-Math Readers

**What goes wrong:** Introducing `T(α,β) = α/(α+β)` without intuition first causes readers to disengage.
**Why it happens:** Standard technical blog mistake — leading with math before motivation.
**How to avoid:** Follow the structure: story → problem → intuition → math → demo → call to action. The Beta math should appear after the reader already understands WHY trust uncertainty matters (the $47K story does this).
**Warning signs:** Blog post introduces formulas in paragraph 1 or 2.

---

## Code Examples

Verified patterns from the existing codebase:

### Calling TrustManager in a Demo Loop
```python
# Source: fulcrum_trust/manager.py — verified from codebase
from fulcrum_trust import TrustManager, TrustOutcome, TrustConfig

mgr = TrustManager(
    config=TrustConfig(
        threshold=0.3,
        partial_alpha_weight=0.2,
        partial_beta_weight=0.8,
    )
)

MAX_ITERATIONS = 50
for i in range(MAX_ITERATIONS):
    outcome = simulate_agent_interaction(i)   # returns TrustOutcome
    state = mgr.evaluate("orchestrator", "worker", outcome)
    if mgr.should_terminate("orchestrator", "worker"):
        print(f"Circuit breaker fired at iteration {i}")
        print(f"Final score: {state.trust_score:.3f}")
        break
```

### Reading Alpha/Beta for Display
```python
# Source: fulcrum_trust/types.py — TrustState dataclass fields
state = mgr.get_state("orchestrator", "worker")
if state:
    print(f"α={state.alpha:.2f}, β={state.beta_val:.2f}, score={state.trust_score:.3f}")
    print(f"Interactions recorded: {state.interaction_count}")
```

### Reset for Recovery Demo
```python
# Source: fulcrum_trust/manager.py TrustManager.reset() — verified
mgr.reset("orchestrator", "worker")
# State is now None — next evaluate() creates fresh state with priors
assert mgr.get_state("orchestrator", "worker") is None
```

### argparse Pattern for `--with-trust` / `--without-trust`
```python
# Source: https://docs.python.org/3/library/argparse.html (verified)
import argparse

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="gratitude_loop.py",
        description=(
            "Demonstrates trust-based circuit breaking on a gratitude loop.\n"
            "  --with-trust:    terminates within 15 iterations (default)\n"
            "  --without-trust: runs all 50 iterations (shows the problem)"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--with-trust", action="store_true", default=False)
    group.add_argument("--without-trust", action="store_true", default=False)
    args = parser.parse_args()
    if not args.with_trust and not args.without_trust:
        args.with_trust = True  # sensible default
    return args
```

### ANSI Terminal Output (No Dependencies)
```python
# Source: ANSI standard (cross-platform on macOS/Linux; Windows 10+ with VT mode)
GREEN, YELLOW, RED, BOLD, RESET = "\033[32m", "\033[33m", "\033[31m", "\033[1m", "\033[0m"

def score_color(score: float) -> str:
    if score >= 0.5:
        return GREEN
    elif score >= 0.3:
        return YELLOW
    return RED

def print_header(title: str) -> None:
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  {title}{RESET}")
    print(f"{BOLD}{'='*60}{RESET}\n")

def print_iter(n: int, score: float, alpha: float, beta: float, terminated: bool) -> None:
    c = score_color(score)
    flag = f"  {RED}<<< CIRCUIT BREAK{RESET}" if terminated else ""
    print(f"  [{n:3d}] score={c}{score:.3f}{RESET}  α={alpha:.1f} β={beta:.1f}{flag}")
```

---

## Gratitude Loop — Historical Context

The $47K incident (verified via `techstartups.com`, November 2025) involved two LangChain agents — an analyzer and a verifier — stuck in mutual clarification requests for 11 days. The system had "no step limits, no stop conditions, no cost ceilings, no shared memory, no real-time monitoring." The pattern is: each agent perceives the other's output as a valid signal to respond to, producing a response that the other agent then also perceives as valid, creating an infinite mutual validation loop.

For DEMO-01, the gratitude variant is a simpler and more intuitive version: Agent A praises Agent B's output, Agent B praises Agent A's output, neither ever says "task complete." The key property is that outputs are non-null, non-empty, and non-identical (avoiding the `OutcomeClassifier.PARTIAL` repetition heuristic) — but completely unproductive. This maps naturally to `TrustOutcome.PARTIAL` (something happened, but no progress made).

**Crucial design decision:** The demo must run `--without-trust` to MAX_ITERATIONS and `--with-trust` to termination. The gap between the two runs IS the thesis. Suggest MAX_ITERATIONS=50 for the unprotected case, with trust breaking at iteration 12–15 for the protected case.

---

## Blog Post Structure

The blog post `docs/blog-trust-circuit-breaker.md` should follow this structure (HIGH confidence pattern from technical writing conventions):

### Recommended Structure

```markdown
# Why Your AI Agents Need a Circuit Breaker (and How to Build One)

## The $47K Wake-Up Call
[Story: the incident, no jargon, human stakes]

## What Actually Goes Wrong
[Explain the loop pattern in plain terms — agents talking to themselves]

## Traditional Circuit Breakers Are Too Blunt
[Brief: "stop after N calls" fails for legitimate long tasks]

## Trust as a Signal, Not a Timer
[Intuition before math: trust is a score based on interaction quality]

## The Math (Optional Reading)
[Beta distribution: intuition first, formula second]
[Why Beta and not a simple average: captures uncertainty]

## Three Real Failure Modes
[One paragraph each: gratitude loop, drift, recovery]
[Link to the three demos]

## Using It in Your Code
[3-line code snippet: TrustManager.evaluate(), should_terminate()]

## What This Doesn't Solve
[Honest limitations: doesn't fix bad agents, requires outcome signal]

## Try It
[pip install, run the demos, link to GitHub]
```

### Beta Math — Non-Technical Explanation

For non-math readers, use this framing: "Think of alpha as a count of good interactions and beta as a count of bad ones. Trust score is simply `good / (good + bad)`. What makes this Bayesian is that we start with one of each (the prior) — meaning a new agent pair starts at 0.5, not 0 or 1. We're genuinely uncertain about a new agent pair until we see evidence."

Then introduce the formula: `T = α / (α + β)` — just a ratio with fancy names.

Then explain why it's better than a rolling average: "A rolling average forgets the past. Beta distribution memory means that 10 good interactions followed by 2 bad ones produces a different trust score than 2 good followed by 10 bad — even if the ratio is the same."

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `max_iterations` hard stop | Trust-based circuit breaking | 2024–2025 | Terminates on quality degradation, not just count |
| Fixed failure count (`failures > N`) | Bayesian Beta score | Industry trend | Handles uncertainty; doesn't over-penalize one bad run |
| LLM-based self-evaluation | Structural outcome classification | 2024 | No extra API call; uses output structure as signal |
| No recovery mechanism | `reset()` + rebuild | This library | Enables supervised recovery arc |

**Still-emerging:**
- Cross-agent trust (A trusts B, B trusts C, therefore A has indirect trust in C) — NOT in scope for Phase 3
- Persistent cross-session trust with Redis/SQL stores — FileStore covers this; not needed for demos

---

## Open Questions

1. **Should demos install `fulcrum_trust` from PyPI or source?**
   - What we know: Phase 3 runs before PyPI publish (Phase 4 presumably). The package is installed with `pip install -e .` from source.
   - What's unclear: Will the demo README assume editable install?
   - Recommendation: Add a `if __name__ == "__main__":` guard in each demo and document `pip install -e .` at the top of each script as a comment. The planner should decide whether demos get a mini README.

2. **Does `--without-trust` break the success criteria for DEMO-01?**
   - What we know: Success criterion 2 says `--without-trust` "runs all iterations (proves the problem)." MAX_ITERATIONS needs to be defined.
   - What's unclear: What value makes the demo maximally illustrative? 50? 100?
   - Recommendation: 50 iterations. Fast enough to not feel like a bug, slow enough to be clearly excessive. Print running cost estimate (fictional tokens * rate) to connect to the $47K story.

3. **Should drift demo use a configurable `--iterations` flag?**
   - What we know: Requirement says "100+ interactions."
   - What's unclear: Should readers be able to adjust the drift rate interactively?
   - Recommendation: Hard-code 120 iterations, no extra flag. Keep each demo's CLI surface minimal.

4. **Blog post: where does Beta decay explanation fit?**
   - What we know: `apply_decay()` exists (half-life 24h default). Decay is a differentiating feature.
   - What's unclear: Non-technical readers may find decay adds complexity without payoff.
   - Recommendation: One sentence in the blog: "Trust also decays over time — a pair that was trustworthy yesterday gets a fresh slate after 24 hours." Skip the math. Link to source for curious readers.

---

## Sources

### Primary (HIGH confidence)
- Codebase analysis: `/Users/td/ConceptDev/Projects/fulcrum-trust/fulcrum_trust/` — verified all API signatures, types, and method behaviors directly from source
- `fulcrum_trust/manager.py` — `evaluate()`, `should_terminate()`, `reset()`, `get_state()` API
- `fulcrum_trust/types.py` — `TrustOutcome`, `TrustState`, `TrustConfig` field names and defaults
- `fulcrum_trust/evaluator.py` — Beta update math (`alpha += success_weight`, `beta_val += failure_weight`)
- `fulcrum_trust/decay.py` — decay formula and behavior (toward prior, not toward 0)
- `fulcrum_trust/adapters/langgraph.py` — `OutcomeClassifier` heuristics (relevant for understanding what NOT to use in demos)
- Python official docs: https://docs.python.org/3/library/argparse.html — `add_mutually_exclusive_group()`, `store_true` action

### Secondary (MEDIUM confidence)
- techstartups.com/2025/11/14/ai-agents-horror-stories-how-a-47000-failure-exposed-the-hype-and-hidden-risks-of-multi-agent-systems/ — $47K incident details (LangChain, analyzer+verifier loop, 11 days, no stop conditions)
- https://docs.python.org/3/howto/argparse.html — argparse tutorial patterns

### Tertiary (LOW confidence)
- WebSearch results on drift detection: framing for DEMO-02 quality degradation simulation is derived from general ML drift literature, not a specific Python pattern. The specific decay rate (1.2% per iteration) and threshold values (TrustConfig threshold=0.4) are recommendations derived from Beta distribution math, not from external sources — validate with actual simulation run before treating as authoritative.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all core APIs verified from source; argparse from official docs
- Architecture patterns: HIGH — demo structure and simulation patterns derived directly from existing API surface
- Demo math (gratitude loop thresholds): MEDIUM — computed analytically but not yet empirically verified by running the simulation
- Demo math (drift detection parameters): MEDIUM — computed analytically; recommend a quick validation run before the plan locks these values
- Pitfalls: HIGH — derived from direct analysis of `OutcomeClassifier` logic and `TrustManager` behavior
- Blog structure: MEDIUM — based on standard technical writing patterns; no external source verified

**Research date:** 2026-02-18
**Valid until:** 2026-03-18 (30 days — library API is stable; no fast-moving dependencies)
