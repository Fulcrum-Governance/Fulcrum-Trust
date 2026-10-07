from __future__ import annotations

import math

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

    def test_opened_at_default_is_none(self) -> None:
        state = TrustState(pair_id="abc", agent_a="a", agent_b="b")
        assert state.opened_at is None


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

    def test_default_recovery_cooldown_is_none(self) -> None:
        assert TrustConfig().recovery_cooldown_seconds is None

    def test_valid_recovery_cooldown(self) -> None:
        cfg = TrustConfig(recovery_cooldown_seconds=60.0)
        assert cfg.recovery_cooldown_seconds == pytest.approx(60.0)

    def test_zero_recovery_cooldown_raises(self) -> None:
        with pytest.raises(ValueError, match="recovery_cooldown_seconds"):
            TrustConfig(recovery_cooldown_seconds=0.0)

    def test_negative_recovery_cooldown_raises(self) -> None:
        with pytest.raises(ValueError, match="recovery_cooldown_seconds"):
            TrustConfig(recovery_cooldown_seconds=-1.0)

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
        """Non-positive alpha_prior is rejected even when alpha_max is set."""
        with pytest.raises(ValueError, match="alpha_prior"):
            TrustConfig(alpha_prior=0.0, alpha_max=5.0)
        with pytest.raises(ValueError, match="alpha_prior"):
            TrustConfig(alpha_prior=-1.0, alpha_max=5.0)

    def test_nonpositive_alpha_prior_raises_without_alpha_max(self) -> None:
        """alpha_prior=0 is rejected unconditionally (0.3.1 hardening)."""
        with pytest.raises(ValueError, match="alpha_prior"):
            TrustConfig(alpha_prior=0.0)

    # --- 0.3.1 validation hardening (FUL-209) -------------------------------

    _REQUIRED_NUMERIC_FIELDS = (
        "threshold",
        "half_life_seconds",
        "alpha_prior",
        "beta_prior",
        "success_weight",
        "failure_weight",
        "partial_alpha_weight",
        "partial_beta_weight",
    )
    _OPTIONAL_NUMERIC_FIELDS = ("recovery_cooldown_seconds", "alpha_max")
    _POSITIVE_FIELDS = (
        "alpha_prior",
        "beta_prior",
        "success_weight",
        "failure_weight",
        "partial_alpha_weight",
        "partial_beta_weight",
    )
    _NONFINITE = (math.nan, math.inf, -math.inf)
    _NONPOSITIVE = (0.0, -1.0, -0.5)

    @pytest.mark.parametrize(
        "field_name", _REQUIRED_NUMERIC_FIELDS + _OPTIONAL_NUMERIC_FIELDS
    )
    @pytest.mark.parametrize("value", _NONFINITE, ids=["nan", "inf", "-inf"])
    def test_nonfinite_numeric_field_raises(
        self, field_name: str, value: float
    ) -> None:
        """NaN/inf/-inf in any numeric field is rejected, naming the field."""
        with pytest.raises(ValueError, match=f"{field_name} must be finite"):
            TrustConfig(**{field_name: value})

    @pytest.mark.parametrize("field_name", _POSITIVE_FIELDS)
    @pytest.mark.parametrize("value", _NONPOSITIVE, ids=["0", "-1", "-0.5"])
    def test_nonpositive_prior_or_weight_raises(
        self, field_name: str, value: float
    ) -> None:
        """Priors and outcome weights must be strictly positive."""
        with pytest.raises(ValueError, match=f"{field_name} must be positive"):
            TrustConfig(**{field_name: value})

    @pytest.mark.parametrize("field_name", _REQUIRED_NUMERIC_FIELDS)
    def test_smallest_positive_values_accepted(self, field_name: str) -> None:
        """Boundary: tiny-but-positive finite values remain constructible."""
        cfg = TrustConfig(**{field_name: 1e-9})
        assert getattr(cfg, field_name) == pytest.approx(1e-9)

    def test_threshold_exactly_one_raises(self) -> None:
        """Boundary: threshold=1.0 is outside the open interval (0, 1)."""
        with pytest.raises(ValueError, match="threshold"):
            TrustConfig(threshold=1.0)

    def test_threshold_just_below_one_accepted(self) -> None:
        cfg = TrustConfig(threshold=1.0 - 1e-9)
        assert cfg.threshold == pytest.approx(1.0 - 1e-9)

    def test_infinite_alpha_max_raises(self) -> None:
        """alpha_max=inf is a non-finite knob, not an 'unbounded cap' alias."""
        with pytest.raises(ValueError, match="alpha_max must be finite"):
            TrustConfig(alpha_max=math.inf)

    def test_error_message_names_rejected_field(self) -> None:
        """Each field's ValueError names itself, not a sibling field."""
        with pytest.raises(ValueError, match="beta_prior"):
            TrustConfig(beta_prior=0.0)
        with pytest.raises(ValueError, match="partial_beta_weight"):
            TrustConfig(partial_beta_weight=-0.1)
        with pytest.raises(ValueError, match="half_life_seconds"):
            TrustConfig(half_life_seconds=math.nan)


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
