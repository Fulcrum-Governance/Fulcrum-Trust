"""
Drift Detection Demo — fulcrum-trust
======================================
An agent starts performing well but gradually degrades over 120 iterations.
Trust-based circuit breaking detects the drift and terminates before catastrophic failure.

Quality mapping:
  >= 0.7  ->  TrustOutcome.SUCCESS   (healthy performance)
   0.3-0.7 ->  TrustOutcome.PARTIAL  (degrading performance)
  < 0.3   ->  TrustOutcome.FAILURE   (poor performance)

Run:
    pip install -e .
    python examples/drift_detection.py
"""

from __future__ import annotations

import sys

from fulcrum_trust import TrustConfig, TrustManager, TrustOutcome
from fulcrum_trust.types import TrustState

# ── ANSI colours (no external library) ───────────────────────────────────────
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
BOLD = "\033[1m"
RESET = "\033[0m"

# ── Simulation parameters ─────────────────────────────────────────────────────
MAX_ITERATIONS = 120
DECAY_PER_ITER = 0.015  # quality drops 1.5% per iteration
AGENT_ORCHESTRATOR = "orchestrator"
AGENT_WORKER = "worker"


# ── Quality simulation ────────────────────────────────────────────────────────


def simulate_quality(iteration: int) -> float:
    """Quality degrades linearly. Reaches PARTIAL zone at iter ~20, FAILURE at iter ~47."""
    return max(0.0, 1.0 - DECAY_PER_ITER * iteration)


def quality_to_outcome(quality: float) -> TrustOutcome:
    """Map quality score to TrustOutcome."""
    if quality >= 0.7:
        return TrustOutcome.SUCCESS
    elif quality >= 0.3:
        return TrustOutcome.PARTIAL
    return TrustOutcome.FAILURE


def quality_label(quality: float) -> str:
    if quality >= 0.7:
        return f"{GREEN}GOOD{RESET}"
    elif quality >= 0.3:
        return f"{YELLOW}DEGRADING{RESET}"
    return f"{RED}POOR{RESET}"


# ── Output helpers ────────────────────────────────────────────────────────────


def score_color(score: float) -> str:
    if score >= 0.5:
        return GREEN
    elif score >= 0.4:
        return YELLOW
    return RED


def print_header(title: str) -> None:
    print(f"\n{BOLD}{'=' * 65}{RESET}")
    print(f"{BOLD}  {title}{RESET}")
    print(f"{BOLD}{'=' * 65}{RESET}\n")


def print_iter(
    n: int,
    quality: float,
    outcome: TrustOutcome,
    state: TrustState,
    terminated: bool,
) -> None:
    c = score_color(state.trust_score)
    flag = f"  {RED}<<< CIRCUIT BREAK{RESET}" if terminated else ""
    ql = quality_label(quality)
    print(
        f"  [{n:3d}] quality={quality:.2f} {ql}  "
        f"trust={c}{state.trust_score:.3f}{RESET}  "
        f"α={state.alpha:.1f}  β={state.beta_val:.1f}"
        f"{flag}"
    )


# ── Main demo ─────────────────────────────────────────────────────────────────


def run_drift_demo() -> None:
    print_header("DRIFT DETECTION DEMO")
    print(
        "  An agent gradually degrades."
        " Trust catches the drift before catastrophic failure."
    )
    print(
        f"  Config: threshold=0.4, {MAX_ITERATIONS} iterations,"
        f" quality decay={DECAY_PER_ITER}/iter\n"
    )
    print("  Quality zones: >= 0.7 SUCCESS | 0.3-0.7 PARTIAL | < 0.3 FAILURE\n")

    mgr = TrustManager(config=TrustConfig(threshold=0.4))

    broke = False
    final_state: TrustState | None = None
    terminated_at = MAX_ITERATIONS

    for i in range(MAX_ITERATIONS):
        quality = simulate_quality(i)
        outcome = quality_to_outcome(quality)
        state = mgr.evaluate(AGENT_ORCHESTRATOR, AGENT_WORKER, outcome)
        terminated = mgr.should_terminate(AGENT_ORCHESTRATOR, AGENT_WORKER)
        print_iter(i, quality, outcome, state, terminated)
        final_state = state
        if terminated:
            terminated_at = i
            broke = True
            break

    print()
    print(f"{BOLD}{'=' * 65}{RESET}")
    if broke and final_state is not None:
        print(
            f"{RED}{BOLD}  DRIFT DETECTED"
            f" — Circuit break fired at iteration {terminated_at}{RESET}"
        )
        print(f"  Final trust score: {final_state.trust_score:.3f} (threshold: 0.40)")
        quality_at_break = simulate_quality(terminated_at)
        print(f"  Agent quality at break: {quality_at_break:.2f}")
        print(f"  Interactions recorded: {final_state.interaction_count}")
        print(
            f"\n  Trust caught degradation"
            f" {MAX_ITERATIONS - terminated_at} iterations before max."
        )
        print(
            f"  Without circuit breaking,"
            f" {MAX_ITERATIONS - terminated_at} more poor-quality"
            f" interactions would have occurred."
        )
    else:
        print(
            f"{YELLOW}{BOLD}  Demo ran all {MAX_ITERATIONS} iterations"
            f" without triggering circuit break.{RESET}"
        )
        print("  Check TrustConfig threshold or decay rate if this is unexpected.")
    print(f"{BOLD}{'=' * 65}{RESET}\n")


if __name__ == "__main__":
    run_drift_demo()
    sys.exit(0)
