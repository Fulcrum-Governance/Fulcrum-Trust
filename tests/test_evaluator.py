from __future__ import annotations
import pytest
from fulcrum_trust.evaluator import TrustEvaluator, make_pair_id
from fulcrum_trust.types import TrustConfig, TrustOutcome


class TestMakePairId:
    def test_order_independent(self) -> None:
        """pair_id('a','b') == pair_id('b','a') (TRUST-05)."""
        assert make_pair_id("agent-a", "agent-b") == make_pair_id("agent-b", "agent-a")

    def test_different_pairs_different_ids(self) -> None:
        assert make_pair_id("a", "b") != make_pair_id("a", "c")

    def test_id_is_16_hex_chars(self) -> None:
        pid = make_pair_id("a", "b")
        assert len(pid) == 16
        assert all(c in "0123456789abcdef" for c in pid)

    def test_deterministic(self) -> None:
        assert make_pair_id("x", "y") == make_pair_id("x", "y")


class TestTrustEvaluator:
    def test_new_state_starts_at_half(self) -> None:
        """Fresh state trust_score = 0.5 (TRUST-01)."""
        ev = TrustEvaluator()
        state = ev.new_state("a", "b")
        assert state.trust_score == pytest.approx(0.5)

    def test_new_state_uses_config_priors(self) -> None:
        cfg = TrustConfig(alpha_prior=2.0, beta_prior=2.0)
        ev = TrustEvaluator(cfg)
        state = ev.new_state("a", "b")
        assert state.alpha == pytest.approx(2.0)
        assert state.beta_val == pytest.approx(2.0)

    def test_success_increments_alpha(self) -> None:
        """SUCCESS increases alpha, raising trust_score (TRUST-02)."""
        ev = TrustEvaluator()
        state = ev.new_state("a", "b")
        ev.update(state, TrustOutcome.SUCCESS)
        assert state.alpha == pytest.approx(2.0)
        assert state.trust_score > 0.5

    def test_failure_increments_beta(self) -> None:
        """FAILURE increases beta_val, lowering trust_score (TRUST-02)."""
        ev = TrustEvaluator()
        state = ev.new_state("a", "b")
        ev.update(state, TrustOutcome.FAILURE)
        assert state.beta_val == pytest.approx(2.0)
        assert state.trust_score < 0.5

    def test_partial_increments_both(self) -> None:
        """PARTIAL adds 0.5 to alpha and beta_val (TRUST-02)."""
        ev = TrustEvaluator()
        state = ev.new_state("a", "b")
        ev.update(state, TrustOutcome.PARTIAL)
        assert state.alpha == pytest.approx(1.5)
        assert state.beta_val == pytest.approx(1.5)
        assert state.trust_score == pytest.approx(0.5)  # balanced

    def test_interaction_count_increments(self) -> None:
        ev = TrustEvaluator()
        state = ev.new_state("a", "b")
        ev.update(state, TrustOutcome.SUCCESS)
        ev.update(state, TrustOutcome.SUCCESS)
        assert state.interaction_count == 2

    def test_two_failures_trigger_circuit_break(self) -> None:
        """2 failures -> trust=0.25 < threshold=0.3 -> circuit break (TRUST-03)."""
        ev = TrustEvaluator()
        state = ev.new_state("a", "b")
        ev.update(state, TrustOutcome.FAILURE)
        ev.update(state, TrustOutcome.FAILURE)
        # alpha=1, beta_val=3, trust=0.25
        assert state.trust_score == pytest.approx(0.25)
        assert ev.is_below_threshold(state) is True

    def test_not_below_threshold_on_success(self) -> None:
        ev = TrustEvaluator()
        state = ev.new_state("a", "b")
        ev.update(state, TrustOutcome.SUCCESS)
        assert ev.is_below_threshold(state) is False

    def test_custom_threshold(self) -> None:
        cfg = TrustConfig(threshold=0.6)
        ev = TrustEvaluator(cfg)
        state = ev.new_state("a", "b")
        # trust_score=0.5 < threshold=0.6 -> below threshold
        assert ev.is_below_threshold(state) is True

    def test_custom_weights(self) -> None:
        cfg = TrustConfig(success_weight=2.0, failure_weight=3.0)
        ev = TrustEvaluator(cfg)
        state = ev.new_state("a", "b")
        ev.update(state, TrustOutcome.SUCCESS)
        assert state.alpha == pytest.approx(3.0)  # 1.0 + 2.0
        ev.update(state, TrustOutcome.FAILURE)
        assert state.beta_val == pytest.approx(4.0)  # 1.0 + 3.0
