"""Cooldown-gated HALF_OPEN recovery probe (FUL-195).

Exercises the opt-in four-state recovery machine enabled by
``TrustConfig.recovery_cooldown_seconds``. With the cooldown set, recovery from
OPEN routes through an observable HALF_OPEN probe state rather than jumping
straight to CLOSED. With the cooldown unset (``None``, the default) behavior is
unchanged — see the regression test at the bottom and the existing suites in
``test_manager_circuit_persistence.py`` / ``test_ipc_bridge.py``.

Determinism follows the established pattern (no clock mock): decay is neutralized
with a huge half-life, and the cooldown anchor (``opened_at``) is back-dated on
the stored state and ``put()`` back to simulate elapsed time.
"""

from __future__ import annotations

import time

import pytest

from fulcrum_trust.evaluator import make_pair_id
from fulcrum_trust.ipc.bridge import CircuitState
from fulcrum_trust.manager import TrustManager
from fulcrum_trust.stores.file import FileStore
from fulcrum_trust.types import TrustConfig, TrustOutcome, TrustState

# Cooldown-gated config; huge half-life neutralizes decay over a fast test.
_COOLDOWN = TrustConfig(
    threshold=0.3, recovery_cooldown_seconds=60.0, half_life_seconds=1_000_000.0
)
# Long cooldown: recovery cannot elapse within a test → gate always holds OPEN.
_LONG_COOLDOWN = TrustConfig(
    threshold=0.3, recovery_cooldown_seconds=3600.0, half_life_seconds=1_000_000.0
)
# Direct-recovery baseline (cooldown unset) with the same no-decay half-life.
_DIRECT = TrustConfig(threshold=0.3, half_life_seconds=1_000_000.0)


class RecordingBridge:
    """In-memory IPC bridge that records publish_state calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, CircuitState, float, str]] = []

    def publish_state(
        self,
        agent_id: str,
        state: CircuitState,
        *,
        trust_score: float = 0.0,
        pair_id: str = "",
    ) -> None:
        self.calls.append((agent_id, state, trust_score, pair_id))

    def close(self) -> None:
        pass


def _open_circuit(tm: TrustManager, a: str = "a", b: str = "b") -> TrustState:
    """Drive two FAILUREs to push trust below threshold (alpha=1, beta=3 → 0.25)."""
    tm.evaluate(a, b, TrustOutcome.FAILURE)
    opened = tm.evaluate(a, b, TrustOutcome.FAILURE)
    assert opened.circuit_state == "OPEN"
    return opened


def _backdate_opened_at(
    tm: TrustManager, seconds_ago: float, a: str = "a", b: str = "b"
) -> None:
    """Rewind the stored opened_at to simulate cooldown elapsing, then persist."""
    st = tm.get_state(a, b)
    assert st is not None
    st.opened_at = time.time() - seconds_ago
    tm._store.put(st.pair_id, st)


class TestCooldownGatedRecovery:
    def test_full_walk_closed_open_halfopen_closed(self) -> None:
        """CLOSED → OPEN → HALF_OPEN → CLOSED across four evaluations."""
        tm = TrustManager(config=_COOLDOWN)

        opened = _open_circuit(tm)
        assert opened.circuit_state == "OPEN"
        assert opened.opened_at is not None  # anchor recorded on the open edge

        # Cooldown elapses.
        _backdate_opened_at(tm, 100.0)

        # OPEN → HALF_OPEN: time-gated admission (independent of the outcome).
        half = tm.evaluate("a", "b", TrustOutcome.SUCCESS)
        assert half.circuit_state == "HALF_OPEN"

        # HALF_OPEN → CLOSED: probe success (trust ≥ threshold).
        closed = tm.evaluate("a", "b", TrustOutcome.SUCCESS)
        assert closed.circuit_state == "CLOSED"

    def test_halfopen_to_open_probe_failure_restarts_cooldown(self) -> None:
        """HALF_OPEN → OPEN when the probe finds trust still below threshold."""
        tm = TrustManager(config=_COOLDOWN)
        _open_circuit(tm)
        _backdate_opened_at(tm, 100.0)

        # OPEN → HALF_OPEN (time-gated), trust still below (alpha=1, beta=4 = 0.2).
        half = tm.evaluate("a", "b", TrustOutcome.FAILURE)
        assert half.circuit_state == "HALF_OPEN"

        before_reopen = time.time()
        reopened = tm.evaluate("a", "b", TrustOutcome.FAILURE)
        assert reopened.circuit_state == "OPEN"
        # Cooldown restarted: opened_at is ~now, not the back-dated value.
        assert reopened.opened_at is not None
        assert reopened.opened_at >= before_reopen - 1.0

    def test_cooldown_not_elapsed_stays_open(self) -> None:
        """Even after trust recovers, OPEN holds until the cooldown elapses."""
        bridge = RecordingBridge()
        tm = TrustManager(config=_LONG_COOLDOWN, ipc_bridge=bridge)
        _open_circuit(tm)
        bridge.calls.clear()

        # Trust recovers (alpha=2, beta=3 = 0.4 ≥ 0.3) but 3600s has not elapsed.
        still_open = tm.evaluate("a", "b", TrustOutcome.SUCCESS)
        assert still_open.circuit_state == "OPEN"
        # No transition → no IPC publish this evaluation.
        assert bridge.calls == []

    def test_ipc_publishes_evaluating_on_open_to_halfopen(self) -> None:
        """The OPEN → HALF_OPEN edge publishes EVALUATING=1 for both agents."""
        bridge = RecordingBridge()
        tm = TrustManager(config=_COOLDOWN, ipc_bridge=bridge)
        _open_circuit(tm)
        _backdate_opened_at(tm, 100.0)
        bridge.calls.clear()

        tm.evaluate("a", "b", TrustOutcome.SUCCESS)  # OPEN → HALF_OPEN

        evaluating = [c for c in bridge.calls if c[1] == CircuitState.EVALUATING]
        assert {c[0] for c in evaluating} == {"a", "b"}
        assert all(int(c[1]) == 1 for c in evaluating)  # EVALUATING is the int 1

    def test_opened_at_persisted_and_restored(self, tmp_path: object) -> None:
        """opened_at round-trips through the FileStore serializer."""
        path = tmp_path / "trust.json"  # type: ignore[operator]
        tm1 = TrustManager(store=FileStore(path), config=_COOLDOWN)
        opened = _open_circuit(tm1)
        assert opened.opened_at is not None
        saved = opened.opened_at

        tm2 = TrustManager(store=FileStore(path), config=_COOLDOWN)
        reloaded = tm2.get_state("a", "b")
        assert reloaded is not None
        assert reloaded.circuit_state == "OPEN"
        assert reloaded.opened_at == pytest.approx(saved)

    def test_open_without_opened_at_is_adopted(self) -> None:
        """A pre-opened_at OPEN state is adopted: opened_at is stamped, then it
        recovers via HALF_OPEN once the fresh cooldown elapses. Doubles as the
        old-disk / regime-switch back-compat proof."""
        tm = TrustManager(config=_COOLDOWN)
        pid = make_pair_id("a", "b")
        legacy = TrustState(
            pair_id=pid,
            agent_a="a",
            agent_b="b",
            alpha=1.0,
            beta_val=3.0,
            last_updated=time.time() - 100.0,
            circuit_state="OPEN",
            opened_at=None,
        )
        tm._store.put(pid, legacy)

        # First evaluation adopts: stamps opened_at, holds OPEN (no premature probe).
        adopted = tm.evaluate("a", "b", TrustOutcome.SUCCESS)
        assert adopted.circuit_state == "OPEN"
        assert adopted.opened_at is not None

        # Once the freshly stamped cooldown elapses, recovery proceeds.
        _backdate_opened_at(tm, 100.0)
        half = tm.evaluate("a", "b", TrustOutcome.SUCCESS)
        assert half.circuit_state == "HALF_OPEN"

    def test_terminated_stays_put_under_cooldown(self) -> None:
        """TERMINATED is sticky even in the cooldown regime (else branch)."""
        tm = TrustManager(config=_COOLDOWN)
        tm.evaluate("a", "b", TrustOutcome.SUCCESS)
        tm.terminate("a", "b")
        assert tm.get_state("a", "b").circuit_state == "TERMINATED"  # type: ignore[union-attr]

        after = tm.evaluate("a", "b", TrustOutcome.SUCCESS)
        assert after.circuit_state == "TERMINATED"


class TestDefaultNoneRegression:
    def test_direct_recovery_never_enters_halfopen(self) -> None:
        """With cooldown unset, OPEN → CLOSED is direct — HALF_OPEN never seen."""
        bridge = RecordingBridge()
        tm = TrustManager(config=_DIRECT, ipc_bridge=bridge)
        _open_circuit(tm)

        # Single SUCCESS recovers directly (alpha=2, beta=3 = 0.4 ≥ 0.3).
        recovered = tm.evaluate("a", "b", TrustOutcome.SUCCESS)
        assert recovered.circuit_state == "CLOSED"
        assert recovered.opened_at is None  # None path never records opened_at

        # No EVALUATING/HALF_OPEN was ever published.
        assert all(c[1] != CircuitState.EVALUATING for c in bridge.calls)
