from __future__ import annotations

import fakeredis
import pytest

from fulcrum_trust.ipc.bridge import (
    CircuitState,
    IPCBridge,
    NullBridge,
    circuit_state_from_str,
)
from fulcrum_trust.ipc.redis_bridge import RedisIPCBridge
from fulcrum_trust.manager import TrustManager
from fulcrum_trust.types import TrustConfig, TrustOutcome


# ---------------------------------------------------------------------------
# Recording bridge for TrustManager integration tests
# ---------------------------------------------------------------------------
class RecordingBridge:
    """In-memory bridge that records publish_state calls."""

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


# ---------------------------------------------------------------------------
# CircuitState enum tests
# ---------------------------------------------------------------------------
class TestCircuitStateValues:
    def test_trusted_is_zero(self) -> None:
        assert int(CircuitState.TRUSTED) == 0

    def test_evaluating_is_one(self) -> None:
        assert int(CircuitState.EVALUATING) == 1

    def test_isolated_is_two(self) -> None:
        assert int(CircuitState.ISOLATED) == 2

    def test_terminated_is_three(self) -> None:
        assert int(CircuitState.TERMINATED) == 3

    def test_all_values(self) -> None:
        assert [int(s) for s in CircuitState] == [0, 1, 2, 3]


class TestCircuitStateFromStr:
    @pytest.mark.parametrize(
        "input_str,expected",
        [
            ("CLOSED", CircuitState.TRUSTED),
            ("OPEN", CircuitState.ISOLATED),
            ("HALF_OPEN", CircuitState.EVALUATING),
            ("TERMINATED", CircuitState.TERMINATED),
            ("unknown", CircuitState.TRUSTED),
            ("", CircuitState.TRUSTED),
            ("garbage", CircuitState.TRUSTED),
        ],
    )
    def test_mapping(self, input_str: str, expected: CircuitState) -> None:
        assert circuit_state_from_str(input_str) == expected


# ---------------------------------------------------------------------------
# NullBridge tests
# ---------------------------------------------------------------------------
class TestNullBridge:
    def test_publish_state_noop(self) -> None:
        bridge = NullBridge()
        # Should not raise.
        bridge.publish_state("agent-1", CircuitState.ISOLATED, trust_score=0.1)

    def test_close_noop(self) -> None:
        bridge = NullBridge()
        bridge.close()  # Should not raise.


# ---------------------------------------------------------------------------
# RedisIPCBridge tests (using fakeredis)
# ---------------------------------------------------------------------------
class TestRedisIPCBridgePublishState:
    def test_writes_correct_key_and_value(self) -> None:
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        bridge = self._make_bridge(fake_redis)

        bridge.publish_state("agent-abc", CircuitState.ISOLATED, trust_score=0.2)

        key = "agent:agent-abc:circuit_state"
        val = fake_redis.get(key)
        assert val == "2", f"Expected '2' (ISOLATED), got {val!r}"

    def test_sets_ttl(self) -> None:
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        bridge = self._make_bridge(fake_redis, ttl=3600)

        bridge.publish_state("agent-ttl", CircuitState.TRUSTED)

        key = "agent:agent-ttl:circuit_state"
        ttl = fake_redis.ttl(key)
        assert ttl > 0, f"Expected positive TTL, got {ttl}"
        assert ttl <= 3600

    def test_all_states_serialized_correctly(self) -> None:
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        bridge = self._make_bridge(fake_redis)

        for state in CircuitState:
            agent = f"agent-{state.name.lower()}"
            bridge.publish_state(agent, state)
            val = fake_redis.get(f"agent:{agent}:circuit_state")
            assert val == str(int(state))

    @staticmethod
    def _make_bridge(
        fake_redis: fakeredis.FakeRedis, ttl: int = 86400
    ) -> RedisIPCBridge:
        """Create a RedisIPCBridge with an injected fakeredis client."""
        bridge = object.__new__(RedisIPCBridge)
        bridge._redis = fake_redis
        bridge._ttl = ttl
        bridge._nats_url = None
        bridge._nats_client = None
        return bridge


class TestRedisIPCBridgeGetState:
    def test_reads_correct_state(self) -> None:
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        bridge = TestRedisIPCBridgePublishState._make_bridge(fake_redis)

        fake_redis.set("agent:agent-read:circuit_state", "3")
        result = bridge.get_state("agent-read")
        assert result == CircuitState.TERMINATED

    def test_missing_key_returns_none(self) -> None:
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        bridge = TestRedisIPCBridgePublishState._make_bridge(fake_redis)

        result = bridge.get_state("nonexistent")
        assert result is None


# ---------------------------------------------------------------------------
# TrustManager + IPC integration tests
# ---------------------------------------------------------------------------
class TestManagerCircuitTransitionClosedToOpen:
    def test_failures_trigger_isolated_publish(self) -> None:
        """Feed failures until below threshold → bridge called with ISOLATED for both agents."""
        bridge = RecordingBridge()
        cfg = TrustConfig(threshold=0.3)
        tm = TrustManager(config=cfg, ipc_bridge=bridge)

        # Two failures bring trust below 0.3: alpha=1, beta=3 → score=0.25
        tm.evaluate("agent-a", "agent-b", TrustOutcome.FAILURE)
        tm.evaluate("agent-a", "agent-b", TrustOutcome.FAILURE)

        # Should have published ISOLATED for both agents.
        isolated_calls = [c for c in bridge.calls if c[1] == CircuitState.ISOLATED]
        agent_ids = {c[0] for c in isolated_calls}
        assert "agent-a" in agent_ids, f"agent-a not in isolated calls: {bridge.calls}"
        assert "agent-b" in agent_ids, f"agent-b not in isolated calls: {bridge.calls}"


class TestManagerCircuitTransitionOpenToClosed:
    def test_recovery_triggers_trusted_publish(self) -> None:
        """After being below threshold, successes push back above → TRUSTED published."""
        bridge = RecordingBridge()
        cfg = TrustConfig(threshold=0.3)
        tm = TrustManager(config=cfg, ipc_bridge=bridge)

        # Drive below threshold.
        tm.evaluate("a", "b", TrustOutcome.FAILURE)
        tm.evaluate("a", "b", TrustOutcome.FAILURE)

        # Clear call log to focus on recovery.
        bridge.calls.clear()

        # Drive back above threshold with successes.
        # After 2 failures + 3 successes: alpha=4, beta=3 → score≈0.571 > 0.3
        tm.evaluate("a", "b", TrustOutcome.SUCCESS)
        tm.evaluate("a", "b", TrustOutcome.SUCCESS)
        tm.evaluate("a", "b", TrustOutcome.SUCCESS)

        trusted_calls = [c for c in bridge.calls if c[1] == CircuitState.TRUSTED]
        agent_ids = {c[0] for c in trusted_calls}
        assert "a" in agent_ids, f"agent 'a' not in trusted calls: {bridge.calls}"
        assert "b" in agent_ids, f"agent 'b' not in trusted calls: {bridge.calls}"


class TestManagerNoTransitionNoPublish:
    def test_no_state_change_no_publish(self) -> None:
        """When score stays above threshold, no bridge calls."""
        bridge = RecordingBridge()
        cfg = TrustConfig(threshold=0.3)
        tm = TrustManager(config=cfg, ipc_bridge=bridge)

        # Successes keep score above threshold; circuit stays CLOSED.
        tm.evaluate("a", "b", TrustOutcome.SUCCESS)
        tm.evaluate("a", "b", TrustOutcome.SUCCESS)
        tm.evaluate("a", "b", TrustOutcome.SUCCESS)

        assert bridge.calls == [], f"Expected no bridge calls, got {bridge.calls}"


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------
class TestIPCBridgeProtocol:
    def test_null_bridge_satisfies_protocol(self) -> None:
        assert isinstance(NullBridge(), IPCBridge)

    def test_redis_bridge_satisfies_protocol(self) -> None:
        fake_redis = fakeredis.FakeRedis(decode_responses=True)
        bridge = TestRedisIPCBridgePublishState._make_bridge(fake_redis)
        assert isinstance(bridge, IPCBridge)

    def test_recording_bridge_satisfies_protocol(self) -> None:
        assert isinstance(RecordingBridge(), IPCBridge)
