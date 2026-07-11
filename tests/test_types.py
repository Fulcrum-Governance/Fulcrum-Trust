from __future__ import annotations

import pytest

from fulcrum_trust.types import TrustCircuitOpen, TrustConfig, TrustOutcome, TrustState


class TestTrustOutcome:
    def test_values_are_strings(self) -> None:
        assert TrustOutcome.SUCCESS.value == "success"
        assert TrustOutcome.FAILURE.value == "failure"
        assert TrustOutcome.PARTIAL.value == "partial"

    def test_string_comparison(self) -> None:
        assert TrustOutcome.SUCCESS == "success"


class TestTrustState:
    def test_initial_trust_score_is_half(self) -> None:
        """Uninformative prior alpha=1,beta=1 yields trust_score=0.5 (TRUST-01)."""
        state = TrustState(pair_id="abc", agent_a="a", agent_b="b")
        assert state.trust_score == pytest.approx(0.5)

    def test_trust_score_after_successes(self) -> None:
        state = TrustState(
            pair_id="abc", agent_a="a", agent_b="b", alpha=3.0, beta_val=1.0
        )
        assert state.trust_score == pytest.approx(0.75)

    def test_trust_score_after_failures(self) -> None:
        state = TrustState(
            pair_id="abc", agent_a="a", agent_b="b", alpha=1.0, beta_val=3.0
        )
        assert state.trust_score == pytest.approx(0.25)

    def test_interaction_count_defaults_to_zero(self) -> None:
        state = TrustState(pair_id="abc", agent_a="a", agent_b="b")
        assert state.interaction_count == 0

    def test_last_updated_is_set_on_creation(self) -> None:
        import time

        before = time.time()
        state = TrustState(pair_id="abc", agent_a="a", agent_b="b")
        after = time.time()
        assert before <= state.last_updated <= after

    def test_circuit_state_default_is_closed(self) -> None:
        state = TrustState(pair_id="abc", agent_a="a", agent_b="b")
        assert state.circuit_state == "CLOSED"

    def test_circuit_state_is_string(self) -> None:
        state = TrustState(pair_id="abc", agent_a="a", agent_b="b")
        assert isinstance(state.circuit_state, str)


class TestTrustConfig:
    def test_default_threshold(self) -> None:
        cfg = TrustConfig()
        assert cfg.threshold == pytest.approx(0.3)

    def test_default_half_life(self) -> None:
        cfg = TrustConfig()
        assert cfg.half_life_seconds == pytest.approx(86400.0)

    def test_default_priors(self) -> None:
        cfg = TrustConfig()
        assert cfg.alpha_prior == pytest.approx(1.0)
        assert cfg.beta_prior == pytest.approx(1.0)

    def test_invalid_threshold_raises(self) -> None:
        with pytest.raises(ValueError, match="threshold"):
            TrustConfig(threshold=0.0)

    def test_threshold_above_one_raises(self) -> None:
        with pytest.raises(ValueError, match="threshold"):
            TrustConfig(threshold=1.5)

    def test_invalid_half_life_raises(self) -> None:
        with pytest.raises(ValueError, match="half_life"):
            TrustConfig(half_life_seconds=-1.0)

    def test_zero_half_life_raises(self) -> None:
        with pytest.raises(ValueError, match="half_life"):
            TrustConfig(half_life_seconds=0.0)

    def test_custom_threshold(self) -> None:
        cfg = TrustConfig(threshold=0.5)
        assert cfg.threshold == pytest.approx(0.5)

    def test_default_alpha_max_is_none(self) -> None:
        """alpha_max defaults to None — unbounded alpha, prior behavior (T1a)."""
        cfg = TrustConfig()
        assert cfg.alpha_max is None

    def test_alpha_max_stored_when_valid(self) -> None:
        cfg = TrustConfig(alpha_max=20.0)
        assert cfg.alpha_max == pytest.approx(20.0)

    def test_alpha_max_below_prior_raises(self) -> None:
        """alpha_max < alpha_prior is rejected (T1a validation)."""
        with pytest.raises(ValueError, match="alpha_max"):
            TrustConfig(alpha_max=0.5)  # default alpha_prior=1.0

    def test_alpha_max_equal_prior_is_legal_boundary(self) -> None:
        """alpha_max == alpha_prior freezes success accrual (legal, degenerate)."""
        cfg = TrustConfig(alpha_prior=2.0, alpha_max=2.0)
        assert cfg.alpha_max == pytest.approx(2.0)

    def test_alpha_max_with_nonpositive_prior_raises(self) -> None:
        """When alpha_max is set, alpha_prior must be strictly positive."""
        with pytest.raises(ValueError, match="alpha_max"):
            TrustConfig(alpha_prior=0.0, alpha_max=5.0)
        with pytest.raises(ValueError, match="alpha_max"):
            TrustConfig(alpha_prior=-1.0, alpha_max=5.0)

    def test_none_alpha_max_skips_prior_validation(self) -> None:
        """Regression: alpha_prior=0 stays constructible while alpha_max is unset."""
        cfg = TrustConfig(alpha_prior=0.0)
        assert cfg.alpha_max is None


class TestTrustCircuitOpen:
    def test_is_exception_subclass(self) -> None:
        exc = TrustCircuitOpen(pair_id="abc", trust_score=0.2, threshold=0.3)
        assert isinstance(exc, Exception)

    def test_attributes_accessible(self) -> None:
        exc = TrustCircuitOpen(pair_id="abc", trust_score=0.2, threshold=0.3)
        assert exc.pair_id == "abc"
        assert exc.trust_score == pytest.approx(0.2)
        assert exc.threshold == pytest.approx(0.3)

    def test_str_contains_pair_id_score_threshold(self) -> None:
        exc = TrustCircuitOpen(pair_id="abc", trust_score=0.2, threshold=0.3)
        msg = str(exc)
        assert "abc" in msg
        assert "0.200" in msg
        assert "0.300" in msg

    def test_can_be_raised_and_caught(self) -> None:
        with pytest.raises(TrustCircuitOpen) as exc_info:
            raise TrustCircuitOpen(pair_id="test", trust_score=0.1, threshold=0.3)
        assert exc_info.value.pair_id == "test"
