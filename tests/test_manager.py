from __future__ import annotations

import time

import pytest

from fulcrum_trust import TrustConfig, TrustManager, TrustOutcome
from fulcrum_trust.stores.file import FileStore
from fulcrum_trust.stores.memory import MemoryStore


class TestGetTrustScore:
    def test_unknown_pair_returns_half(self) -> None:
        """Success criterion: TrustManager().get_trust_score('a','b') == 0.5 (TRUST-01)."""
        tm = TrustManager()
        assert tm.get_trust_score("agent-a", "agent-b") == pytest.approx(0.5)

    def test_order_independent(self) -> None:
        """get_trust_score('a','b') == get_trust_score('b','a') (TRUST-05)."""
        tm = TrustManager()
        tm.evaluate("agent-a", "agent-b", TrustOutcome.SUCCESS)
        assert tm.get_trust_score("agent-a", "agent-b") == pytest.approx(
            tm.get_trust_score("agent-b", "agent-a")
        )

    def test_increases_after_success(self) -> None:
        """SUCCESS raises trust_score above 0.5 (TRUST-02)."""
        tm = TrustManager()
        tm.evaluate("a", "b", TrustOutcome.SUCCESS)
        assert tm.get_trust_score("a", "b") > 0.5

    def test_decreases_after_failure(self) -> None:
        """FAILURE lowers trust_score below 0.5 (TRUST-02)."""
        tm = TrustManager()
        tm.evaluate("a", "b", TrustOutcome.FAILURE)
        assert tm.get_trust_score("a", "b") < 0.5

    def test_custom_config_affects_score(self) -> None:
        """Custom alpha_prior changes default score (TRUST-01)."""
        cfg = TrustConfig(alpha_prior=3.0, beta_prior=1.0)
        tm = TrustManager(config=cfg)
        # 3/(3+1) = 0.75
        assert tm.get_trust_score("a", "b") == pytest.approx(0.75)


class TestShouldTerminate:
    def test_unknown_pair_returns_false(self) -> None:
        """No history = no termination (innocent until proven guilty)."""
        tm = TrustManager()
        assert tm.should_terminate("a", "b") is False

    def test_two_failures_trigger_termination(self) -> None:
        """2 FAILUREs -> trust=0.25 < threshold=0.3 -> True (TRUST-03)."""
        tm = TrustManager()
        tm.evaluate("a", "b", TrustOutcome.FAILURE)
        tm.evaluate("a", "b", TrustOutcome.FAILURE)
        assert tm.should_terminate("a", "b") is True

    def test_success_prevents_termination(self) -> None:
        """A success keeps trust above threshold (TRUST-03)."""
        tm = TrustManager()
        tm.evaluate("a", "b", TrustOutcome.SUCCESS)
        assert tm.should_terminate("a", "b") is False

    def test_custom_threshold_lower(self) -> None:
        """Lower threshold = more tolerant circuit breaker (TRUST-03)."""
        cfg = TrustConfig(threshold=0.1)
        tm = TrustManager(config=cfg)
        tm.evaluate("a", "b", TrustOutcome.FAILURE)
        tm.evaluate("a", "b", TrustOutcome.FAILURE)
        # trust=0.25 > threshold=0.1 -> no termination
        assert tm.should_terminate("a", "b") is False

    def test_order_independent(self) -> None:
        """should_terminate('a','b') == should_terminate('b','a') (TRUST-05)."""
        tm = TrustManager()
        tm.evaluate("a", "b", TrustOutcome.FAILURE)
        tm.evaluate("a", "b", TrustOutcome.FAILURE)
        assert tm.should_terminate("a", "b") == tm.should_terminate("b", "a")


class TestEvaluate:
    def test_returns_trust_state(self) -> None:
        tm = TrustManager()
        state = tm.evaluate("a", "b", TrustOutcome.SUCCESS)
        assert state.trust_score > 0.5

    def test_consecutive_evaluations_accumulate(self) -> None:
        """Multiple evaluations build history (TRUST-02 + TRUST-05)."""
        tm = TrustManager()
        tm.evaluate("a", "b", TrustOutcome.SUCCESS)
        tm.evaluate("a", "b", TrustOutcome.SUCCESS)
        tm.evaluate("a", "b", TrustOutcome.SUCCESS)
        state = tm.get_state("a", "b")
        assert state is not None
        assert state.interaction_count == 3

    def test_partial_outcome_is_balanced(self) -> None:
        """PARTIAL keeps trust near 0.5 (TRUST-02)."""
        tm = TrustManager()
        tm.evaluate("a", "b", TrustOutcome.PARTIAL)
        score = tm.get_trust_score("a", "b")
        assert score == pytest.approx(0.5, abs=0.01)


class TestReset:
    def test_reset_returns_to_half(self) -> None:
        tm = TrustManager()
        tm.evaluate("a", "b", TrustOutcome.FAILURE)
        tm.evaluate("a", "b", TrustOutcome.FAILURE)
        assert tm.should_terminate("a", "b") is True
        tm.reset("a", "b")
        assert tm.get_trust_score("a", "b") == pytest.approx(0.5)
        assert tm.should_terminate("a", "b") is False


class TestDecayIntegration:
    def test_decay_applied_on_evaluate(self) -> None:
        """Decay toward 0.5 is applied before new outcome on evaluate() (TRUST-04)."""
        cfg = TrustConfig(half_life_seconds=1.0)  # 1 second half-life for fast test
        tm = TrustManager(config=cfg)
        tm.evaluate("a", "b", TrustOutcome.SUCCESS)
        tm.evaluate("a", "b", TrustOutcome.SUCCESS)
        tm.evaluate("a", "b", TrustOutcome.SUCCESS)
        score_before = tm.get_trust_score("a", "b")
        assert score_before > 0.7

        # Simulate passage of many half-lives by manipulating last_updated
        state = tm.get_state("a", "b")
        assert state is not None
        state.last_updated = time.time() - 100.0  # 100 seconds = 100 half-lives
        tm._store.put(state.pair_id, state)

        score_after = tm.get_trust_score("a", "b")
        assert score_after < score_before, "Decay should reduce trust toward 0.5"
        assert score_after == pytest.approx(0.5, abs=0.01)


class TestFileStorePersistence:
    def test_persists_across_manager_instances(
        self, tmp_path: pytest.TempPathFactory
    ) -> None:
        """TrustManager with FileStore preserves history across instances (TRUST-05, TRUST-06)."""
        path = tmp_path / "trust.json"
        tm1 = TrustManager(store=FileStore(path))
        tm1.evaluate("a", "b", TrustOutcome.SUCCESS)
        tm1.evaluate("a", "b", TrustOutcome.SUCCESS)
        score1 = tm1.get_trust_score("a", "b")

        tm2 = TrustManager(store=FileStore(path))
        score2 = tm2.get_trust_score("a", "b")
        assert score2 == pytest.approx(score1, abs=0.001)
        assert tm2.get_state("a", "b") is not None


class TestRaiseOnBreakIntegration:
    def test_raise_on_break_parameter_exists(self) -> None:
        """evaluate() accepts raise_on_break keyword argument."""
        tm = TrustManager()
        state = tm.evaluate("a", "b", TrustOutcome.SUCCESS, raise_on_break=False)
        assert state.trust_score > 0.5


class TestAsyncFlush:
    def test_async_flush_true_creates_flusher(self) -> None:
        tm = TrustManager(async_flush=True)
        assert tm._flusher is not None
        tm._flusher.shutdown()

    def test_async_flush_false_no_flusher(self) -> None:
        tm = TrustManager()
        assert tm._flusher is None

    def test_async_flush_default_is_false(self) -> None:
        tm = TrustManager(async_flush=False)
        assert tm._flusher is None

    def test_async_flush_routes_through_flusher(self) -> None:
        """With async_flush=True, evaluate() enqueues instead of direct store write."""
        store = MemoryStore()
        tm = TrustManager(store=store, async_flush=True)
        tm.evaluate("a", "b", TrustOutcome.SUCCESS)
        # Direct store should be empty (queued in flusher)
        from fulcrum_trust.evaluator import make_pair_id

        pid = make_pair_id("a", "b")
        assert store.get(pid) is None  # not written directly
        # Force flush
        tm._flusher.flush()
        assert store.get(pid) is not None  # now persisted
        tm._flusher.shutdown()
