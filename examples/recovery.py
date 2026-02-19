"""
Recovery Demo — fulcrum-trust
================================
Shows the full trust lifecycle: degradation -> circuit break -> intervention -> recovery.

Phase 1 - DEGRADATION:  Agent produces failures. Trust drops. Circuit breaks.
Phase 2 - INTERVENTION: Human reviews agent. TrustManager.reset() clears history.
Phase 3 - RECOVERY:     Agent performs well. Trust rebuilds above threshold.

Run:
    pip install -e .
    python examples/recovery.py
"""
from __future__ import annotations

import sys

from fulcrum_trust import TrustConfig, TrustManager, TrustOutcome
from fulcrum_trust.types import TrustState

# ── ANSI colours (no external library) ───────────────────────────────────────
GREEN  = "\033[32m"
YELLOW = "\033[33m"
RED    = "\033[31m"
CYAN   = "\033[36m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

# ── Constants ─────────────────────────────────────────────────────────────────
AGENT_ORCHESTRATOR = "orchestrator"
AGENT_WORKER = "worker"


# ── Output helpers ────────────────────────────────────────────────────────────

def score_color(score: float) -> str:
    if score >= 0.5:
        return GREEN
    elif score >= 0.3:
        return YELLOW
    return RED


def print_phase_header(phase: str, color: str) -> None:
    print(f"\n{BOLD}{color}{'─'*55}{RESET}")
    print(f"{BOLD}{color}  PHASE: {phase}{RESET}")
    print(f"{BOLD}{color}{'─'*55}{RESET}\n")


def print_trust_row(
    n: int,
    state: TrustState,
    outcome: TrustOutcome,
    terminated: bool,
) -> None:
    c = score_color(state.trust_score)
    outcome_label = {
        TrustOutcome.SUCCESS: f"{GREEN}SUCCESS{RESET}",
        TrustOutcome.FAILURE: f"{RED}FAILURE{RESET}",
        TrustOutcome.PARTIAL: f"{YELLOW}PARTIAL{RESET}",
    }[outcome]
    flag = f"  {RED}<<< CIRCUIT OPEN{RESET}" if terminated else ""
    print(
        f"  [{n:2d}] {outcome_label}  "
        f"trust={c}{state.trust_score:.3f}{RESET}  "
        f"α={state.alpha:.1f}  β={state.beta_val:.1f}"
        f"{flag}"
    )


# ── Main demo ─────────────────────────────────────────────────────────────────

def run_recovery_demo() -> None:
    print(f"\n{BOLD}{'='*55}{RESET}")
    print(f"{BOLD}  RECOVERY DEMO — fulcrum-trust{RESET}")
    print(f"{BOLD}{'='*55}{RESET}")
    print("\n  Trust degrades -> circuit breaks -> agent is reset -> trust rebuilds.\n")

    mgr = TrustManager(
        config=TrustConfig(threshold=0.3)
    )

    # ── Phase 1: Degradation ──────────────────────────────────────────────────
    print_phase_header("1. DEGRADATION", RED)
    print("  Worker agent produces repeated failures.\n")

    broke = False
    for i in range(12):
        state = mgr.evaluate(AGENT_ORCHESTRATOR, AGENT_WORKER, TrustOutcome.FAILURE)
        terminated = mgr.should_terminate(AGENT_ORCHESTRATOR, AGENT_WORKER)
        print_trust_row(i, state, TrustOutcome.FAILURE, terminated)
        if terminated:
            broke = True
            break

    if broke:
        print(
            f"\n  {RED}{BOLD}Circuit breaker opened."
            f" Orchestrator halted all worker calls.{RESET}"
        )
    else:
        print(
            f"\n  {YELLOW}Circuit breaker did not open"
            f" — check threshold configuration.{RESET}"
        )

    # ── Phase 2: Intervention ─────────────────────────────────────────────────
    print_phase_header("2. INTERVENTION", CYAN)
    print("  Human operator reviews the worker agent.")
    print("  Root cause identified. Worker is patched and redeployed.")
    print("  Clearing trust history...\n")

    mgr.reset(AGENT_ORCHESTRATOR, AGENT_WORKER)
    state_after_reset = mgr.get_state(AGENT_ORCHESTRATOR, AGENT_WORKER)
    assert state_after_reset is None, "reset() should clear state"

    score_after_reset = mgr.get_trust_score(AGENT_ORCHESTRATOR, AGENT_WORKER)
    print(
        f"  Trust state cleared. Score reverts to prior:"
        f" {GREEN}{score_after_reset:.3f}{RESET}"
    )
    print(f"  (Uninformative prior: α=1.0, β=1.0 -> score=0.500)\n")

    # ── Phase 3: Recovery ─────────────────────────────────────────────────────
    print_phase_header("3. RECOVERY", GREEN)
    print("  Worker agent now performs consistently well.\n")

    for i in range(15):
        state = mgr.evaluate(AGENT_ORCHESTRATOR, AGENT_WORKER, TrustOutcome.SUCCESS)
        terminated = mgr.should_terminate(AGENT_ORCHESTRATOR, AGENT_WORKER)
        print_trust_row(i, state, TrustOutcome.SUCCESS, terminated)

    # ── Final summary ─────────────────────────────────────────────────────────
    final_state = mgr.get_state(AGENT_ORCHESTRATOR, AGENT_WORKER)
    print()
    print(f"{BOLD}{'='*55}{RESET}")
    print(f"{BOLD}  RECOVERY COMPLETE{RESET}")
    if final_state is not None:
        c = score_color(final_state.trust_score)
        print(
            f"  Final trust score: {c}{final_state.trust_score:.3f}{RESET}"
            f"  (threshold: 0.30)"
        )
        print(f"  Interactions in recovery: {final_state.interaction_count}")
        if final_state.trust_score > 0.5:
            print(
                f"  {GREEN}Trust fully restored above prior (0.5)."
                f" Agent is healthy.{RESET}"
            )
        elif final_state.trust_score > 0.3:
            print(
                f"  {YELLOW}Trust in warning zone."
                f" More successful interactions needed.{RESET}"
            )
        else:
            print(f"  {RED}Trust still below threshold. Recovery incomplete.{RESET}")
    print(f"{BOLD}{'='*55}{RESET}\n")


if __name__ == "__main__":
    run_recovery_demo()
    sys.exit(0)
