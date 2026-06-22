"""Persistence of automatic circuit-state transitions through evaluate().

Regression coverage for the bug where TrustManager.evaluate() persisted state
to the store BEFORE applying the circuit-state transition. Copy-on-put stores
(FileStore, FulcrumStore) therefore captured the PRE-transition circuit_state,
so an automatic CLOSED->OPEN (or OPEN->CLOSED) edge was never durably
persisted / shipped. MemoryStore stores by reference and masked the bug.

These tests assert that the SINGLE persistence call happens AFTER the
transition, so the final circuit_state is what lands on disk / on the wire.
Trust-math semantics (alpha/beta/trust_score/decay) are unchanged.
"""

from __future__ import annotations

from typing import Any

from fulcrum_trust import TrustConfig, TrustManager, TrustOutcome
from fulcrum_trust.stores.file import FileStore
from fulcrum_trust.stores.fulcrum import FulcrumStore

# Large half-life so lazy decay is negligible across these fast tests; the
# behavior under test is transition persistence, not decay.
_NO_DECAY = TrustConfig(half_life_seconds=1_000_000.0)


class TestFileStoreCircuitStatePersistence:
    def test_open_transition_persisted_to_disk(self, tmp_path: Any) -> None:
        """Automatic CLOSED->OPEN survives a fresh FileStore-backed manager.

        Two FAILUREs drive trust to 0.25 < 0.3, flipping CLOSED->OPEN. A fresh
        TrustManager reading the same file must see circuit_state == 'OPEN'.
        Fails on origin/main (pre-transition CLOSED was persisted).
        """
        path = tmp_path / "trust.json"
        tm1 = TrustManager(store=FileStore(path), config=_NO_DECAY)
        tm1.evaluate("a", "b", TrustOutcome.FAILURE)
        state = tm1.evaluate("a", "b", TrustOutcome.FAILURE)
        assert state.circuit_state == "OPEN"  # in-memory transition applied

        tm2 = TrustManager(store=FileStore(path), config=_NO_DECAY)
        reloaded = tm2.get_state("a", "b")
        assert reloaded is not None
        assert reloaded.circuit_state == "OPEN"

    def test_recovery_transition_persisted_to_disk(self, tmp_path: Any) -> None:
        """From OPEN, recovery above threshold persists OPEN->CLOSED to disk."""
        path = tmp_path / "trust.json"
        tm1 = TrustManager(store=FileStore(path), config=_NO_DECAY)
        tm1.evaluate("a", "b", TrustOutcome.FAILURE)
        opened = tm1.evaluate("a", "b", TrustOutcome.FAILURE)
        assert opened.circuit_state == "OPEN"

        # alpha=1, beta_val=3 -> add a SUCCESS -> 2/5 = 0.4 >= 0.3 -> CLOSED.
        recovered = tm1.evaluate("a", "b", TrustOutcome.SUCCESS)
        assert recovered.circuit_state == "CLOSED"

        tm2 = TrustManager(store=FileStore(path), config=_NO_DECAY)
        reloaded = tm2.get_state("a", "b")
        assert reloaded is not None
        assert reloaded.circuit_state == "CLOSED"


class TestAsyncFlushCircuitStatePersistence:
    def test_open_transition_persisted_via_flusher(self, tmp_path: Any) -> None:
        """Async path: transitioned circuit_state lands on disk after flush.

        The flusher batches writes, so a read-after-write within evaluate() only
        sees a prior outcome once it has been flushed to the store. We flush
        between the two FAILUREs so the second evaluate reads alpha=1/beta_val=2
        and the third (combined) state crosses the threshold. The assertion that
        matters is that the OPEN transition is what reaches disk.
        """
        path = tmp_path / "trust.json"
        tm = TrustManager(store=FileStore(path), config=_NO_DECAY, async_flush=True)
        assert tm._flusher is not None
        try:
            tm.evaluate("a", "b", TrustOutcome.FAILURE)
            tm._flusher.flush()  # make the first failure visible to the next read
            state = tm.evaluate("a", "b", TrustOutcome.FAILURE)
            assert state.circuit_state == "OPEN"  # in-memory transition applied
            tm._flusher.flush()  # push the transitioned state to disk
        finally:
            tm._flusher.shutdown()

        reloaded = FileStore(path).get(state.pair_id)
        assert reloaded is not None
        assert reloaded.circuit_state == "OPEN"


class TestFulcrumStoreCircuitStateShipped:
    def test_shipped_payload_reflects_post_transition_state(
        self, monkeypatch: Any
    ) -> None:
        """FulcrumStore ships the POST-transition circuit_state on the wire.

        Patch _post_event to capture the payload it would ship. The last write
        of the OPEN-triggering evaluate must carry circuit_state == 'OPEN'.
        """
        captured: list[dict[str, Any]] = []

        def _capture(self: FulcrumStore, pair_id: str, state: Any) -> None:
            from dataclasses import asdict

            captured.append(
                {
                    "pair_id": pair_id,
                    "payload": {"payload": {"state": asdict(state)}},
                }
            )

        monkeypatch.setattr(FulcrumStore, "_post_event", _capture)

        store = FulcrumStore(api_key="test-key")
        tm = TrustManager(store=store, config=_NO_DECAY)
        tm.evaluate("a", "b", TrustOutcome.FAILURE)
        tm.evaluate("a", "b", TrustOutcome.FAILURE)  # triggers CLOSED->OPEN

        assert captured, "expected at least one shipped event"
        last = captured[-1]
        assert last["payload"]["payload"]["state"]["circuit_state"] == "OPEN"

    def test_shipped_payload_via_urlopen_reflects_transition(
        self, monkeypatch: Any
    ) -> None:
        """End-to-end: the urlopen-bound request body carries 'OPEN'."""
        import json

        captured_bodies: list[dict[str, Any]] = []

        class _FakeResp:
            def __enter__(self) -> _FakeResp:
                return self

            def __exit__(self, *args: Any) -> None:
                return None

        def _fake_urlopen(request: Any, timeout: float = 0.0) -> _FakeResp:
            captured_bodies.append(json.loads(request.data.decode("utf-8")))
            return _FakeResp()

        monkeypatch.setattr(
            "fulcrum_trust.stores.fulcrum.urllib.request.urlopen", _fake_urlopen
        )

        store = FulcrumStore(api_key="test-key")
        tm = TrustManager(store=store, config=_NO_DECAY)
        tm.evaluate("a", "b", TrustOutcome.FAILURE)
        tm.evaluate("a", "b", TrustOutcome.FAILURE)  # triggers CLOSED->OPEN

        assert captured_bodies, "expected at least one POST body"
        last = captured_bodies[-1]
        assert last["payload"]["state"]["circuit_state"] == "OPEN"


class TestNoTrustMathRegression:
    def test_success_evaluate_leaves_trust_math_unchanged(self, tmp_path: Any) -> None:
        """The reorder must not alter alpha/beta_val/trust_score on a SUCCESS.

        Reference values: from priors alpha=1, beta_val=1, one SUCCESS yields
        alpha=2.0, beta_val=1.0, trust_score=2/3, circuit_state stays CLOSED.
        """
        tm = TrustManager(store=FileStore(tmp_path / "trust.json"), config=_NO_DECAY)
        state = tm.evaluate("a", "b", TrustOutcome.SUCCESS)
        assert state.alpha == 2.0
        assert state.beta_val == 1.0
        assert state.trust_score == 2.0 / 3.0
        assert state.circuit_state == "CLOSED"

        reloaded = TrustManager(
            store=FileStore(tmp_path / "trust.json"), config=_NO_DECAY
        ).get_state("a", "b")
        assert reloaded is not None
        assert reloaded.alpha == 2.0
        assert reloaded.beta_val == 1.0
        assert reloaded.circuit_state == "CLOSED"

    def test_terminate_persists_terminated_to_disk(self, tmp_path: Any) -> None:
        """terminate() still durably writes TERMINATED (unaffected by the fix)."""
        path = tmp_path / "trust.json"
        tm1 = TrustManager(store=FileStore(path), config=_NO_DECAY)
        tm1.evaluate("a", "b", TrustOutcome.SUCCESS)
        tm1.terminate("a", "b")

        tm2 = TrustManager(store=FileStore(path), config=_NO_DECAY)
        reloaded = tm2.get_state("a", "b")
        assert reloaded is not None
        assert reloaded.circuit_state == "TERMINATED"
