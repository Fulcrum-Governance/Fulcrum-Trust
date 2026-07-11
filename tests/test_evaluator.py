from __future__ import annotations

import math
import random

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


class TestAlphaMaxCap:
    """T1a — capped Beta prior bounds worst-case failures-to-detection.

    The engine knob is Implemented here; the corresponding worst-case bound
    is Proved only for the discrete capped Lean model (D4 Theorem 3.9,
    DOI 10.5281/zenodo.19900714). The raw-model constant asserted below
    differs from the Lean witness — see README "Bounded detection latency
    (alpha_max)" for the correspondence note.
    """

    def test_cap_holds_across_any_sequence(self) -> None:
        """alpha never exceeds alpha_max across a long mixed outcome sequence."""
        cap = 5.0
        ev = TrustEvaluator(TrustConfig(alpha_max=cap))
        state = ev.new_state("a", "b")
        rng = random.Random(42)
        outcomes = [TrustOutcome.SUCCESS, TrustOutcome.FAILURE, TrustOutcome.PARTIAL]
        for _ in range(500):
            ev.update(state, rng.choice(outcomes))
            assert state.alpha <= cap

    def test_overshooting_increment_clamps_to_exactly_cap(self) -> None:
        """A single increment past the cap lands exactly on alpha_max."""
        ev = TrustEvaluator(TrustConfig(alpha_max=2.0, success_weight=2.5))
        state = ev.new_state("a", "b")
        ev.update(state, TrustOutcome.SUCCESS)  # 1.0 + 2.5 -> clamped
        assert state.alpha == pytest.approx(2.0)
        ev.update(state, TrustOutcome.PARTIAL)  # +0.5 -> clamped again
        assert state.alpha == pytest.approx(2.0)
        assert state.beta_val == pytest.approx(1.5)  # beta unaffected by cap

    @pytest.mark.parametrize("cap", [2.0, 3.0, 5.0, 20.0, 60.0, 100.0])
    def test_worst_case_failures_to_threshold_is_bounded(self, cap: float) -> None:
        """Failures-to-detection <= ceil(alpha_max*(q-p)/p) for theta = p/q (T1a).

        Raw model: trust = alpha/(alpha+beta) < theta = p/q  iff
        beta > alpha*(q-p)/p. With alpha <= alpha_max and theta = 0.3 = 3/10,
        the circuit opens within ceil(alpha_max*7/3) failures — no matter how
        long the preceding clean history ran.
        """
        p, q = 3, 10  # theta = 0.3, the default threshold
        ev = TrustEvaluator(TrustConfig(alpha_max=cap))
        state = ev.new_state("a", "b")
        # Worst case: drive alpha to the cap with a long clean history.
        for _ in range(int(cap) * 10):
            ev.update(state, TrustOutcome.SUCCESS)
        assert state.alpha == pytest.approx(cap)  # cap held under sustained success
        bound = math.ceil(cap * (q - p) / p)
        failures = 0
        while not ev.is_below_threshold(state):
            ev.update(state, TrustOutcome.FAILURE)
            failures += 1
            assert failures <= bound, f"needed {failures} failures, bound is {bound}"
        assert failures <= bound

    def test_unbounded_alpha_has_no_constant_bound(self) -> None:
        """Contrast: without the cap, clean history buys unbounded failure runway."""
        ev = TrustEvaluator()  # alpha_max=None
        state = ev.new_state("a", "b")
        for _ in range(300):
            ev.update(state, TrustOutcome.SUCCESS)
        capped_bound_for_20 = math.ceil(20.0 * 7 / 3)  # 47
        failures = 0
        while not ev.is_below_threshold(state):
            ev.update(state, TrustOutcome.FAILURE)
            failures += 1
        assert failures > capped_bound_for_20

    def test_default_none_preserves_unbounded_trajectory(self) -> None:
        """Regression: default config reproduces the exact pre-cap trajectory."""
        ev = TrustEvaluator()
        state = ev.new_state("a", "b")
        for _ in range(50):
            ev.update(state, TrustOutcome.SUCCESS)
        assert state.alpha == pytest.approx(51.0)
