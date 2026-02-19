from __future__ import annotations

import dataclasses

from fulcrum_trust.decay import apply_decay
from fulcrum_trust.evaluator import TrustEvaluator, make_pair_id
from fulcrum_trust.stores.base import TrustStore
from fulcrum_trust.stores.memory import MemoryStore
from fulcrum_trust.types import TrustConfig, TrustOutcome, TrustState


class TrustManager:
    """Orchestrates trust evaluation, persistence, and decay.

    Single source of truth for all trust state mutations. Default store is
    MemoryStore (in-process). Pass FileStore for cross-session persistence.

    Args:
        store: Persistence layer. Defaults to MemoryStore.
        config: Trust engine configuration. Defaults to TrustConfig().
    """

    def __init__(
        self,
        store: TrustStore | None = None,
        config: TrustConfig | None = None,
    ) -> None:
        self._config = config if config is not None else TrustConfig()
        self._store: TrustStore = store if store is not None else MemoryStore()
        self._evaluator = TrustEvaluator(self._config)

    def evaluate(self, agent_a: str, agent_b: str, outcome: TrustOutcome) -> TrustState:
        """Record outcome and return updated trust state.

        Applies decay first (lazy decay on read), then records new outcome.

        Args:
            agent_a: First agent identifier.
            agent_b: Second agent identifier. Order does not matter.
            outcome: Interaction result (SUCCESS, FAILURE, or PARTIAL).

        Returns:
            Updated TrustState after decay and Bayesian update.
        """
        pid = make_pair_id(agent_a, agent_b)
        state = self._store.get(pid)
        if state is None:
            state = self._evaluator.new_state(agent_a, agent_b)
        else:
            # Apply decay before recording new evidence
            state = apply_decay(state, self._config.half_life_seconds)
        state = self._evaluator.update(state, outcome)
        self._store.put(pid, state)
        return state

    def get_trust_score(self, agent_a: str, agent_b: str) -> float:
        """Return current trust score (0.5 for unknown pairs).

        Applies decay on read. Does not mutate stored state.

        Args:
            agent_a: First agent identifier.
            agent_b: Second agent identifier. Order does not matter.

        Returns:
            Trust score in range (0, 1). Returns 0.5 for unknown pairs.
        """
        pid = make_pair_id(agent_a, agent_b)
        state = self._store.get(pid)
        if state is None:
            return self._config.alpha_prior / (
                self._config.alpha_prior + self._config.beta_prior
            )
        # Apply decay for accurate current score (read-only, do not persist)
        # Use a copy to avoid mutating the stored state object.
        decayed = apply_decay(
            dataclasses.replace(state), self._config.half_life_seconds
        )
        return decayed.trust_score

    def should_terminate(self, agent_a: str, agent_b: str) -> bool:
        """Return True if trust score is below the circuit break threshold.

        Args:
            agent_a: First agent identifier.
            agent_b: Second agent identifier. Order does not matter.

        Returns:
            True if trust_score < config.threshold (default 0.3).
        """
        pid = make_pair_id(agent_a, agent_b)
        state = self._store.get(pid)
        if state is None:
            return False  # Unknown pair: full trust, no termination
        # Use a copy to avoid mutating the stored state object.
        decayed = apply_decay(
            dataclasses.replace(state), self._config.half_life_seconds
        )
        return self._evaluator.is_below_threshold(decayed)

    def get_state(self, agent_a: str, agent_b: str) -> TrustState | None:
        """Return raw TrustState for a pair, or None if not yet evaluated."""
        pid = make_pair_id(agent_a, agent_b)
        return self._store.get(pid)

    def reset(self, agent_a: str, agent_b: str) -> None:
        """Remove trust history for a pair. Pair reverts to uninformative prior."""
        pid = make_pair_id(agent_a, agent_b)
        self._store.delete(pid)
