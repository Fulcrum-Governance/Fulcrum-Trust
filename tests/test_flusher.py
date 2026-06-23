from __future__ import annotations

import logging
import threading
import time

import pytest

from fulcrum_trust import TrustManager, TrustOutcome
from fulcrum_trust.evaluator import make_pair_id
from fulcrum_trust.flusher import BackgroundFlusher
from fulcrum_trust.stores.file import FileStore
from fulcrum_trust.stores.memory import MemoryStore
from fulcrum_trust.types import TrustState


class _FlakyStore(MemoryStore):
    """MemoryStore whose ``put`` raises for one specific pair_id.

    Used to exercise the flusher's per-item resilience: a single bad write
    must not drop the rest of the batch or kill the background thread.
    """

    def __init__(self, fail_pair_id: str) -> None:
        super().__init__()
        self._fail_pair_id = fail_pair_id
        self.attempts: list[str] = []

    def put(self, pair_id: str, state: TrustState) -> None:
        self.attempts.append(pair_id)
        if pair_id == self._fail_pair_id:
            raise RuntimeError(f"simulated store failure for {pair_id}")
        super().put(pair_id, state)


class TestBackgroundFlusherInit:
    def test_starts_background_thread(self) -> None:
        store = MemoryStore()
        flusher = BackgroundFlusher(store, flush_interval=0.1)
        assert flusher._thread.is_alive()
        flusher.shutdown()

    def test_thread_is_daemon(self) -> None:
        store = MemoryStore()
        flusher = BackgroundFlusher(store, flush_interval=0.1)
        assert flusher._thread.daemon is True
        flusher.shutdown()

    def test_thread_name(self) -> None:
        store = MemoryStore()
        flusher = BackgroundFlusher(store, flush_interval=0.1)
        assert flusher._thread.name == "fulcrum-trust-flusher"
        flusher.shutdown()


class TestEnqueue:
    def test_enqueue_is_nonblocking(self) -> None:
        store = MemoryStore()
        flusher = BackgroundFlusher(store, flush_interval=10.0)  # long interval
        state = TrustState(pair_id="abc", agent_a="a", agent_b="b")
        start = time.monotonic()
        flusher.enqueue(state)
        elapsed = time.monotonic() - start
        assert elapsed < 0.1  # non-blocking
        flusher.shutdown()


class TestFlush:
    def test_flush_persists_queued_events(self) -> None:
        store = MemoryStore()
        flusher = BackgroundFlusher(store, flush_interval=10.0)
        state = TrustState(pair_id="abc", agent_a="a", agent_b="b", alpha=3.0)
        flusher.enqueue(state)
        flusher.flush()
        assert store.get("abc") is not None
        assert store.get("abc").alpha == pytest.approx(3.0)
        flusher.shutdown()

    def test_flush_drains_multiple_events(self) -> None:
        store = MemoryStore()
        flusher = BackgroundFlusher(store, flush_interval=10.0)
        for i in range(5):
            state = TrustState(pair_id=f"pair_{i}", agent_a="a", agent_b="b")
            flusher.enqueue(state)
        flusher.flush()
        assert len(store.all_pairs()) == 5
        flusher.shutdown()


class TestShutdown:
    def test_shutdown_stops_thread(self) -> None:
        store = MemoryStore()
        flusher = BackgroundFlusher(store, flush_interval=0.1)
        assert flusher._thread.is_alive()
        flusher.shutdown()
        assert not flusher._thread.is_alive()

    def test_shutdown_persists_remaining_events(self) -> None:
        store = MemoryStore()
        flusher = BackgroundFlusher(store, flush_interval=0.1)
        state = TrustState(pair_id="abc", agent_a="a", agent_b="b")
        flusher.enqueue(state)
        time.sleep(0.3)  # allow background thread to flush before shutdown
        flusher.shutdown()
        assert store.get("abc") is not None


class TestMaxBatch:
    def test_many_events_all_persisted(self) -> None:
        store = MemoryStore()
        flusher = BackgroundFlusher(store, flush_interval=0.1, max_batch=50)
        for i in range(200):
            state = TrustState(pair_id=f"pair_{i}", agent_a="a", agent_b="b")
            flusher.enqueue(state)
        # Wait for background thread to process
        time.sleep(1.0)
        flusher.shutdown()
        assert len(store.all_pairs()) == 200


class TestFlushInterval:
    def test_auto_flush_on_interval(self) -> None:
        store = MemoryStore()
        flusher = BackgroundFlusher(store, flush_interval=0.2, max_batch=1000)
        state = TrustState(pair_id="abc", agent_a="a", agent_b="b")
        flusher.enqueue(state)
        time.sleep(0.5)  # wait for auto-flush
        assert store.get("abc") is not None
        flusher.shutdown()


class TestThreadSafety:
    def test_concurrent_enqueue_no_data_loss(self) -> None:
        store = MemoryStore()
        flusher = BackgroundFlusher(store, flush_interval=0.1, max_batch=50)
        num_threads = 10
        events_per_thread = 20

        def enqueue_batch(thread_id: int) -> None:
            for i in range(events_per_thread):
                state = TrustState(
                    pair_id=f"t{thread_id}_p{i}", agent_a="a", agent_b="b"
                )
                flusher.enqueue(state)

        threads = [
            threading.Thread(target=enqueue_batch, args=(t,))
            for t in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        flusher.shutdown()
        assert len(store.all_pairs()) == num_threads * events_per_thread


class TestIntegrationAsyncFlush:
    def test_async_flush_with_file_store(
        self, tmp_path: pytest.TempPathFactory
    ) -> None:
        """TrustManager with async_flush=True persists events via FileStore."""
        path = tmp_path / "trust.json"
        store = FileStore(str(path))
        manager = TrustManager(store=store, async_flush=True)

        manager.evaluate("agent_a", "agent_b", TrustOutcome.SUCCESS)

        # Force flush
        assert manager._flusher is not None
        manager._flusher.flush()

        # Read directly from store to verify persistence
        pair_id = make_pair_id("agent_a", "agent_b")
        state = store.get(pair_id)
        assert state is not None
        assert state.interaction_count == 1
        assert state.alpha > 1.0  # success incremented alpha

        manager._flusher.shutdown()


class TestFlusherResilience:
    """A single failing store.put must not drop the rest of the batch."""

    def test_one_bad_write_does_not_drop_good_writes(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        store = _FlakyStore(fail_pair_id="bad")
        flusher = BackgroundFlusher(store, flush_interval=10.0)  # manual flush only

        for pair_id in ("good_0", "bad", "good_1"):
            flusher.enqueue(TrustState(pair_id=pair_id, agent_a="a", agent_b="b"))

        with caplog.at_level(logging.WARNING, logger="fulcrum_trust.flusher"):
            # Must not raise, even though "bad" fails mid-batch.
            flusher.flush()

        # The good writes landed; the bad one did not.
        assert store.get("good_0") is not None
        assert store.get("good_1") is not None
        assert store.get("bad") is None

        # All three were attempted (the failure did not short-circuit the loop).
        assert store.attempts == ["good_0", "bad", "good_1"]

        # The failure was logged with the offending pair_id.
        assert "bad" in caplog.text
        assert flusher.failed_writes == 1

        flusher.shutdown()

    def test_failure_logged_at_warning_or_above(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        store = _FlakyStore(fail_pair_id="bad")
        flusher = BackgroundFlusher(store, flush_interval=10.0)
        flusher.enqueue(TrustState(pair_id="bad", agent_a="a", agent_b="b"))

        with caplog.at_level(logging.WARNING, logger="fulcrum_trust.flusher"):
            flusher.flush()

        failure_records = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert failure_records, "expected a WARNING+ log for the failed write"
        flusher.shutdown()


class TestFlusherThreadSurvival:
    """A store error on the background thread must not kill the thread."""

    def test_thread_survives_store_error_and_keeps_flushing(self) -> None:
        store = _FlakyStore(fail_pair_id="bad")
        # Short interval so the background _run cycle does the persisting.
        flusher = BackgroundFlusher(store, flush_interval=0.05, max_batch=1000)

        # First, enqueue the poison record and let the thread process it.
        flusher.enqueue(TrustState(pair_id="bad", agent_a="a", agent_b="b"))
        deadline = time.monotonic() + 2.0
        while "bad" not in store.attempts and time.monotonic() < deadline:
            time.sleep(0.02)
        assert "bad" in store.attempts, "background thread never attempted the write"

        # The thread must still be alive after swallowing the error.
        assert flusher._thread.is_alive()

        # A subsequently-enqueued good state must still be persisted by the
        # same (surviving) background thread.
        flusher.enqueue(TrustState(pair_id="good", agent_a="a", agent_b="b"))
        deadline = time.monotonic() + 2.0
        while store.get("good") is None and time.monotonic() < deadline:
            time.sleep(0.02)
        assert store.get("good") is not None, (
            "background thread died after a store error — later write lost"
        )
        assert flusher._thread.is_alive()

        flusher.shutdown()


class TestRedisBridgeFailClosedContract:
    """Lock in the intended fail-closed behavior of the canonical Redis write.

    This is the safe contract the flusher fix deliberately does NOT change:
    ``RedisIPCBridge.publish_state`` re-raises on a Redis pipeline error so
    callers cannot silently proceed on a failed canonical write.
    """

    def test_publish_state_reraises_on_pipeline_error(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        from fulcrum_trust.ipc.bridge import CircuitState
        from fulcrum_trust.ipc.redis_bridge import RedisIPCBridge

        class _ExplodingPipeline:
            def set(self, *args: object, **kwargs: object) -> None:
                pass

            def expire(self, *args: object, **kwargs: object) -> None:
                pass

            def execute(self) -> None:
                raise RuntimeError("redis pipeline EXEC failed")

        class _ExplodingRedis:
            def pipeline(self, transaction: bool = True) -> _ExplodingPipeline:
                return _ExplodingPipeline()

        bridge = object.__new__(RedisIPCBridge)
        bridge._redis = _ExplodingRedis()
        bridge._ttl = 86400
        bridge._nats_url = None
        bridge._nats_client = None

        with caplog.at_level(logging.ERROR, logger="fulcrum_trust.ipc"):
            with pytest.raises(RuntimeError, match="EXEC failed"):
                bridge.publish_state("agent-x", CircuitState.ISOLATED, trust_score=0.1)

        assert "fail-closed" in caplog.text
