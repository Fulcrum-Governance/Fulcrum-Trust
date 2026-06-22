from __future__ import annotations

import atexit
import logging
import queue
import threading
import time

from fulcrum_trust.stores.base import TrustStore
from fulcrum_trust.types import TrustState

logger = logging.getLogger("fulcrum_trust.flusher")


class BackgroundFlusher:
    """Thread-safe background flusher for trust state events.

    Accepts TrustState events via a non-blocking queue and persists them
    to the configured store in batches on a background thread. Prevents
    synchronous store I/O from blocking the agent's execution loop.

    Args:
        store: Persistence layer to flush events into.
        flush_interval: Seconds between automatic flushes. Default 5.0.
        max_batch: Maximum events per flush cycle. Default 100.

    Usage::

        flusher = BackgroundFlusher(store=FileStore("trust.json"))
        flusher.enqueue(state)  # non-blocking
        # flushes automatically; also flushes on process exit
    """

    def __init__(
        self,
        store: TrustStore,
        flush_interval: float = 5.0,
        max_batch: int = 100,
    ) -> None:
        self._store = store
        self._flush_interval = flush_interval
        self._max_batch = max_batch
        self.failed_writes = 0  # count of store.put failures (observability)
        self._queue: queue.Queue[TrustState | None] = queue.Queue()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="fulcrum-trust-flusher"
        )
        self._thread.start()
        atexit.register(self.shutdown)

    def enqueue(self, state: TrustState) -> None:
        """Add a TrustState event to the flush queue (non-blocking).

        Args:
            state: Updated TrustState to persist asynchronously.
        """
        self._queue.put_nowait(state)

    def flush(self) -> None:
        """Drain the queue and persist all pending events immediately."""
        batch: list[TrustState] = []
        try:
            while True:
                item = self._queue.get_nowait()
                if item is None:
                    break
                batch.append(item)
        except queue.Empty:
            pass
        self._persist(batch)

    def shutdown(self) -> None:
        """Flush remaining events and stop the background thread gracefully."""
        self._stop_event.set()
        self._queue.put(None)  # sentinel to unblock the thread
        self._thread.join(timeout=10.0)
        self.flush()  # final drain of anything that arrived during join

    def _run(self) -> None:
        """Background thread: drain queue on interval or when batch is full."""
        while not self._stop_event.is_set():
            deadline = time.monotonic() + self._flush_interval
            batch: list[TrustState] = []
            while time.monotonic() < deadline and len(batch) < self._max_batch:
                try:
                    item = self._queue.get(timeout=0.1)
                    if item is None:
                        return  # shutdown sentinel
                    batch.append(item)
                except queue.Empty:
                    pass
            if batch:
                self._persist(batch)

    def _persist(self, batch: list[TrustState]) -> None:
        """Write a batch of TrustState objects to the store.

        Each write is isolated: if ``store.put`` raises for one pair (e.g. a
        disk or serialization error), the failure is logged and the loop
        continues with the rest of the batch. Exceptions are never allowed to
        escape this method, which keeps the daemon ``_run`` thread alive — a
        single bad write must not silently kill the flusher and strand every
        subsequent enqueue.
        """
        for state in batch:
            try:
                self._store.put(state.pair_id, state)
            except Exception:
                self.failed_writes += 1
                logger.exception(
                    "Flusher store.put failed for pair_id=%s — "
                    "dropping this event and continuing",
                    state.pair_id,
                )
