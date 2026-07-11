from __future__ import annotations

import hashlib
import time

from fulcrum_trust.types import TrustConfig, TrustOutcome, TrustState


def make_pair_id(agent_a: str, agent_b: str) -> str:
    """Generate deterministic order-independent pair key (SHA256 prefix)."""
    key = ":".join(sorted([agent_a, agent_b]))
    return hashlib.sha256(key.encode()).hexdigest()[:16]


class TrustEvaluator:
    """Computes Beta(alpha, beta) trust scores. Pure math, no I/O."""

    def __init__(self, config: TrustConfig | None = None) -> None:
        self._config = config if config is not None else TrustConfig()

    def new_state(self, agent_a: str, agent_b: str) -> TrustState:
        """Create a fresh TrustState with uninformative priors."""
        pid = make_pair_id(agent_a, agent_b)
        return TrustState(
            pair_id=pid,
            agent_a=agent_a,
            agent_b=agent_b,
            alpha=self._config.alpha_prior,
            beta_val=self._config.beta_prior,
            last_updated=time.time(),
            interaction_count=0,
        )

    def update(self, state: TrustState, outcome: TrustOutcome) -> TrustState:
        """Apply Bayesian update: increment alpha (success) or beta_val (failure).

        PARTIAL adds half-weight to both, representing mixed evidence.
        When config.alpha_max is set, alpha is clamped to it after the
        increment; a state carrying alpha above a newly configured cap is
        clamped down on its first update. Mutates state in place and returns it.
        """
        cfg = self._config
        if outcome == TrustOutcome.SUCCESS:
            state.alpha += cfg.success_weight
        elif outcome == TrustOutcome.FAILURE:
            state.beta_val += cfg.failure_weight
        elif outcome == TrustOutcome.PARTIAL:
            state.alpha += cfg.partial_alpha_weight
            state.beta_val += cfg.partial_beta_weight
        if cfg.alpha_max is not None:
            state.alpha = min(state.alpha, cfg.alpha_max)
        state.interaction_count += 1
        state.last_updated = time.time()
        return state

    def is_below_threshold(self, state: TrustState) -> bool:
        """Return True if trust_score < threshold (circuit break condition)."""
        return state.trust_score < self._config.threshold
