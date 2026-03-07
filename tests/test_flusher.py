from __future__ import annotations

import threading
import time

import pytest

from fulcrum_trust import TrustManager, TrustOutcome
from fulcrum_trust.evaluator import make_pair_id
from fulcrum_trust.flusher import BackgroundFlusher
from fulcrum_trust.stores.file import FileStore
from fulcrum_trust.stores.memory import MemoryStore
from fulcrum_trust.types import TrustState


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
