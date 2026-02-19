"""
Gratitude Loop Demo — fulcrum-trust
====================================
Two agents praise each other indefinitely with no stop condition.

  --with-trust    TrustManager circuit-breaks within 15 iterations (default)
  --without-trust Loop runs all 50 iterations — shows the $47K problem

Run:
    pip install -e .
    python examples/gratitude_loop.py --with-trust
    python examples/gratitude_loop.py --without-trust
"""
from __future__ import annotations

import argparse
import sys

from fulcrum_trust import TrustConfig, TrustManager, TrustOutcome
from fulcrum_trust.types import TrustState

# ── ANSI colours (no external library) ───────────────────────────────────────
GREEN  = "\033[32m"
YELLOW = "\033[33m"
RED    = "\033[31m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

# ── Simulation constants ──────────────────────────────────────────────────────
MAX_ITERATIONS = 50
AGENT_A = "agent_alpha"
AGENT_B = "agent_beta"

_PRAISE = [
    "Thank you! That was incredibly helpful.",
    "Great point! I completely agree with your assessment.",
    "Excellent work! Your analysis is spot on.",
    "You've really captured the essence of the problem.",
    "I couldn't have said it better myself.",
]


def agent_response(agent_name: str, iteration: int) -> str:
    """Deterministic praise. Always non-empty, always loops. Never advances task."""
    return _PRAISE[iteration % len(_PRAISE)]


# ── Output helpers ────────────────────────────────────────────────────────────

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


def print_iter(n: int, state: TrustState, terminated: bool) -> None:
    c = score_color(state.trust_score)
    flag = f"  {RED}<<< CIRCUIT BREAK{RESET}" if terminated else ""
    print(
        f"  [{n:3d}] score={c}{state.trust_score:.3f}{RESET}"
        f"  α={state.alpha:.1f}  β={state.beta_val:.1f}{flag}"
    )


def print_no_trust_iter(n: int, response_a: str) -> None:
    print(f"  [{n:3d}] {AGENT_A}: \"{response_a[:45]}...\"")


def print_summary(terminated: bool, iterations: int, score: float | None) -> None:
    print()
    print(f"{BOLD}{'='*60}{RESET}")
    if terminated and score is not None:
        print(f"{RED}{BOLD}  TERMINATED: Trust circuit break{RESET}")
        print(f"  After {iterations} iteration(s)")
        print(f"  Final trust score: {score:.3f} (threshold: 0.30)")
        print(
            f"  Estimated tokens saved vs. unchecked run:"
            f" ~{MAX_ITERATIONS - iterations} iterations"
        )
        print(f"  (In production at scale: thousands of API calls avoided)")
    else:
        print(
            f"{RED}{BOLD}  RUNAWAY LOOP: No circuit breaker"
            f" — ran all {iterations} iterations{RESET}"
        )
        print(f"  Nothing stopped this loop. In production, this runs indefinitely.")
        print(f"  The $47K incident ran for 11 days.")
    print(f"{BOLD}{'='*60}{RESET}\n")


# ── Run modes ─────────────────────────────────────────────────────────────────

def run_with_trust() -> None:
    """TrustManager terminates the gratitude loop within 15 iterations."""
    print_header("GRATITUDE LOOP — With Trust Circuit Breaker")
    print("  Config: partial_alpha_weight=0.2, partial_beta_weight=0.8")
    print("  (Gratitude is mostly unproductive — drives beta up faster)\n")

    mgr = TrustManager(
        config=TrustConfig(
            threshold=0.3,
            partial_alpha_weight=0.2,
            partial_beta_weight=0.8,
        )
    )

    final_state: TrustState | None = None
    terminated_at: int = MAX_ITERATIONS - 1
    broke = False

    for i in range(MAX_ITERATIONS):
        # Agents are responsive but never make progress — PARTIAL
        state = mgr.evaluate(AGENT_A, AGENT_B, TrustOutcome.PARTIAL)
        terminated = mgr.should_terminate(AGENT_A, AGENT_B)
        print_iter(i, state, terminated)
        final_state = state
        if terminated:
            terminated_at = i
            broke = True
            break

    score = final_state.trust_score if final_state is not None else 0.5
    print_summary(
        terminated=broke,
        iterations=terminated_at + 1 if broke else MAX_ITERATIONS,
        score=score,
    )


def run_without_trust() -> None:
    """No TrustManager — loop runs all MAX_ITERATIONS. Shows the problem."""
    print_header("GRATITUDE LOOP — Without Trust Circuit Breaker")
    print(f"  Running {MAX_ITERATIONS} iterations with NO stop condition.\n")

    for i in range(MAX_ITERATIONS):
        response_a = agent_response(AGENT_A, i)
        print_no_trust_iter(i, response_a)

    print_summary(terminated=False, iterations=MAX_ITERATIONS, score=None)


# ── CLI ───────────────────────────────────────────────────────────────────────

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
    group.add_argument(
        "--with-trust",
        action="store_true",
        default=False,
        help="Run with TrustManager circuit breaker (default)",
    )
    group.add_argument(
        "--without-trust",
        action="store_true",
        default=False,
        help="Run without circuit breaker (loop runs to completion)",
    )
    args = parser.parse_args()
    if not args.with_trust and not args.without_trust:
        args.with_trust = True  # sensible default: show the solution
    return args


if __name__ == "__main__":
    args = parse_args()
    if args.with_trust:
        run_with_trust()
    else:
        run_without_trust()
    sys.exit(0)
