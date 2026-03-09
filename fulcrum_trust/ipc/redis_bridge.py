from __future__ import annotations

import json
import logging
import time
from typing import Any

from fulcrum_trust.ipc.bridge import CircuitState

logger = logging.getLogger("fulcrum_trust.ipc")

_TTL_SECONDS = 86400  # 24-hour rolling TTL


class RedisIPCBridge:
    """Redis+NATS IPC bridge for trust state synchronization.

    Writes circuit breaker state to Redis using MULTI/EXEC for atomicity.
    Optionally publishes telemetry events to NATS.

    Key schema: ``agent:{agent_id}:circuit_state`` → integer (0-3)

    Requires ``redis`` package. NATS publishing requires ``nats-py``.

    Args:
        redis_url: Redis connection URL (e.g. ``redis://localhost:6379``).
        nats_url: Optional NATS connection URL. If None, NATS publishing
            is skipped (Redis-only mode).
        ttl_seconds: TTL for Redis keys. Default 86400 (24 hours).

    Example::

        bridge = RedisIPCBridge("redis://localhost:6379")
        bridge.publish_state("agent-abc", CircuitState.ISOLATED, trust_score=0.15)
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        nats_url: str | None = None,
        ttl_seconds: int = _TTL_SECONDS,
    ) -> None:
        try:
            import redis as redis_lib
        except ImportError as exc:
            raise ImportError(
                "redis package required for IPC bridge. "
                "Install with: pip install fulcrum-trust[ipc]"
            ) from exc

        self._redis: Any = redis_lib.Redis.from_url(redis_url, decode_responses=True)
        self._ttl = ttl_seconds
        self._nats_url = nats_url
        self._nats_client: Any = None

        if nats_url:
            self._init_nats(nats_url)

    def _init_nats(self, nats_url: str) -> None:
        """Best-effort NATS connection. Failures are logged, not raised."""
        try:
            import nats.aio.client  # noqa: F401

            # NATS py is async — we use a sync wrapper for simplicity
            # in the trust manager's synchronous evaluate() path.
            # Store URL for lazy connection in _publish_nats_event.
            self._nats_url = nats_url
            logger.info("NATS telemetry configured: %s", nats_url)
        except ImportError:
            logger.warning(
                "nats-py not installed. NATS telemetry disabled. "
                "Install with: pip install fulcrum-trust[ipc]"
            )
            self._nats_url = None

    def _redis_key(self, agent_id: str) -> str:
        return f"agent:{agent_id}:circuit_state"

    def publish_state(
        self,
        agent_id: str,
        state: CircuitState,
        *,
        trust_score: float = 0.0,
        pair_id: str = "",
    ) -> None:
        """Atomically write circuit state to Redis and publish NATS telemetry.

        Uses Redis MULTI/EXEC for atomic SET+EXPIRE. NATS publish is
        best-effort — if NATS is delayed or unavailable, Redis state
        is still authoritative.
        """
        key = self._redis_key(agent_id)
        try:
            pipe = self._redis.pipeline(transaction=True)
            pipe.set(key, int(state))
            pipe.expire(key, self._ttl)
            pipe.execute()
        except Exception:
            logger.exception("Redis write failed for %s — fail-closed", key)
            raise

        self._publish_nats_event(agent_id, state, trust_score, pair_id)

    def _publish_nats_event(
        self,
        agent_id: str,
        state: CircuitState,
        trust_score: float,
        pair_id: str,
    ) -> None:
        """Best-effort NATS telemetry publish. Never raises."""
        if not self._nats_url:
            return

        subject = f"fulcrum.trust.agent.{agent_id}.event"
        payload = json.dumps(
            {
                "agent_id": agent_id,
                "circuit_state": int(state),
                "circuit_state_name": state.name,
                "trust_score": round(trust_score, 6),
                "pair_id": pair_id,
                "timestamp": time.time(),
            }
        ).encode()

        try:
            if self._nats_client is None:
                self._connect_nats_sync()
            if self._nats_client is not None:
                self._nats_client.publish(subject, payload)
        except Exception:
            logger.debug("NATS publish failed for %s — continuing", subject)

    def _connect_nats_sync(self) -> None:
        """Lazy synchronous NATS connection using nats-py's sync client."""
        if not self._nats_url:
            return
        try:
            # For sync usage we'll use a simple socket-level publish.
            # nats-py is async-first. For the synchronous TrustManager path,
            # we use a lightweight approach: direct socket publishing.
            # This avoids requiring an event loop in the caller.
            import re
            import socket

            parsed = re.match(r"nats://([^:]+):(\d+)", self._nats_url)
            if not parsed:
                logger.warning("Cannot parse NATS URL: %s", self._nats_url)
                return

            host, port = parsed.group(1), int(parsed.group(2))
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            sock.connect((host, port))
            # Read INFO line
            sock.recv(4096)
            # Send CONNECT
            sock.sendall(b"CONNECT {}\r\n")
            self._nats_client = _SyncNATSPublisher(sock)
        except Exception:
            logger.debug("NATS sync connection failed — telemetry disabled")
            self._nats_client = None

    def get_state(self, agent_id: str) -> CircuitState | None:
        """Read current circuit state from Redis. Returns None if key missing."""
        key = self._redis_key(agent_id)
        try:
            val = self._redis.get(key)
            if val is None:
                return None
            return CircuitState(int(val))
        except Exception:
            logger.exception("Redis read failed for %s", key)
            return None

    def close(self) -> None:
        """Close Redis and NATS connections."""
        try:
            self._redis.close()
        except Exception:
            pass
        if self._nats_client is not None:
            try:
                self._nats_client.close()
            except Exception:
                pass


class _SyncNATSPublisher:
    """Minimal synchronous NATS publisher using raw socket."""

    def __init__(self, sock: Any) -> None:
        self._sock = sock

    def publish(self, subject: str, payload: bytes) -> None:
        msg = f"PUB {subject} {len(payload)}\r\n".encode() + payload + b"\r\n"
        self._sock.sendall(msg)

    def close(self) -> None:
        try:
            self._sock.close()
        except Exception:
            pass
