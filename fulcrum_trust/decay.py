from __future__ import annotations
import math
import time

from fulcrum_trust.types import TrustState


def _decay_factor(elapsed: float, half_life: float) -> float:
    """Compute 0.5^(elapsed/half_life). Returns 1.0 if no time has passed."""
    if elapsed <= 0 or math.isinf(half_life):
        return 1.0
    return float(0.5 ** (elapsed / half_life))


def apply_decay(
    state: TrustState,
    half_life_seconds: float,
) -> TrustState:
    """Decay alpha/beta toward the uninformative prior (1.0) using exponential decay.

    Decay target is 1.0 (NOT 0.0). After many half-lives, trust_score -> 0.5.
    Mutates state in place and returns it.
    """
    elapsed = time.time() - state.last_updated
    factor = _decay_factor(elapsed, half_life_seconds)
    # Decay toward prior (1.0), not toward 0: new_val = 1.0 + (old_val - 1.0) * factor
    state.alpha = 1.0 + (state.alpha - 1.0) * factor
    state.beta_val = 1.0 + (state.beta_val - 1.0) * factor
    return state
