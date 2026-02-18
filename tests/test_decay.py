from __future__ import annotations
import math
import time
import pytest
from fulcrum_trust.decay import apply_decay, _decay_factor
from fulcrum_trust.types import TrustState


class TestDecayFactor:
    def test_no_elapsed_time_returns_one(self) -> None:
        assert _decay_factor(0.0, 86400.0) == pytest.approx(1.0)

    def test_one_half_life_returns_half(self) -> None:
        assert _decay_factor(86400.0, 86400.0) == pytest.approx(0.5)

    def test_two_half_lives_returns_quarter(self) -> None:
        assert _decay_factor(172800.0, 86400.0) == pytest.approx(0.25)

    def test_negative_elapsed_returns_one(self) -> None:
        assert _decay_factor(-100.0, 86400.0) == pytest.approx(1.0)

    def test_infinite_half_life_returns_one(self) -> None:
        assert _decay_factor(86400.0, math.inf) == pytest.approx(1.0)


class TestApplyDecay:
    def _state_with_known_update(self, elapsed_seconds: float) -> TrustState:
        """Create a TrustState whose last_updated is `elapsed_seconds` in the past."""
        state = TrustState(
            pair_id="test",
            agent_a="a",
            agent_b="b",
            alpha=3.0,   # trust_score=0.75 before decay
            beta_val=1.0,
            interaction_count=2,
        )
        state.last_updated = time.time() - elapsed_seconds
        return state

    def test_no_elapsed_no_change(self) -> None:
        """With no time elapsed, alpha/beta are unchanged (TRUST-04)."""
        state = self._state_with_known_update(0.0)
        original_alpha = state.alpha
        apply_decay(state, 86400.0)
        assert state.alpha == pytest.approx(original_alpha)

    def test_one_half_life_moves_halfway_to_prior(self) -> None:
        """After 1 half-life, alpha moves from 3.0 halfway toward 1.0 -> 2.0 (TRUST-04)."""
        state = self._state_with_known_update(86400.0)
        apply_decay(state, 86400.0)
        # alpha: 1.0 + (3.0 - 1.0) * 0.5 = 2.0
        assert state.alpha == pytest.approx(2.0, abs=0.05)

    def test_many_half_lives_converges_to_prior(self) -> None:
        """After many half-lives, trust_score -> 0.5 (not 0.0) (TRUST-04)."""
        state = self._state_with_known_update(86400.0 * 50)
        apply_decay(state, 86400.0)
        # Both alpha and beta_val should be very close to 1.0
        assert state.trust_score == pytest.approx(0.5, abs=0.001)

    def test_decay_target_is_prior_not_zero(self) -> None:
        """Critically: decay toward 1.0, NOT toward 0.0 (TRUST-04)."""
        state = self._state_with_known_update(86400.0 * 100)
        apply_decay(state, 86400.0)
        assert state.alpha >= 0.999
        assert state.beta_val >= 0.999

    def test_beta_val_also_decays(self) -> None:
        """beta_val decays toward 1.0 the same way as alpha (TRUST-04)."""
        state = TrustState(
            pair_id="test",
            agent_a="a",
            agent_b="b",
            alpha=1.0,
            beta_val=5.0,
        )
        state.last_updated = time.time() - 86400.0  # 1 half-life ago
        apply_decay(state, 86400.0)
        # beta_val: 1.0 + (5.0 - 1.0) * 0.5 = 3.0
        assert state.beta_val == pytest.approx(3.0, abs=0.05)

    def test_returns_state(self) -> None:
        """apply_decay returns the same state object (mutates in place)."""
        state = self._state_with_known_update(0.0)
        result = apply_decay(state, 86400.0)
        assert result is state
