from __future__ import annotations

from enum import IntEnum
from typing import Protocol, runtime_checkable


class CircuitState(IntEnum):
    """Redis-serialized circuit breaker states for IPC bridge.

    Values match the Go-side constants in internal/trust/ipc_bridge.go.
    Key schema: agent:{id}:circuit_state

    Four-state model:
    - TRUSTED/EVALUATING/ISOLATED are managed by the trust pipeline (Bayesian evaluation).
    - TERMINATED is an administrative override — set by operator via TrustManager.terminate(),
      not by the trust pipeline. Pair cannot recover without explicit reset.
    """

    TRUSTED = 0  # CLOSED — normal operation
    EVALUATING = 1  # HALF_OPEN — recovery probe after cooldown
    ISOLATED = 2  # OPEN — trust below threshold
    TERMINATED = (
        3  # Administrative kill switch — set by operator, not by trust pipeline
    )


# Mapping from TrustState.circuit_state string to CircuitState int.
_CIRCUIT_STATE_MAP: dict[str, CircuitState] = {
    "CLOSED": CircuitState.TRUSTED,
    "OPEN": CircuitState.ISOLATED,
    "HALF_OPEN": CircuitState.EVALUATING,
    "TERMINATED": CircuitState.TERMINATED,
}


def circuit_state_from_str(state: str) -> CircuitState:
    """Convert TrustState.circuit_state string to CircuitState int."""
    return _CIRCUIT_STATE_MAP.get(state, CircuitState.TRUSTED)


@runtime_checkable
class IPCBridge(Protocol):
    """Interface for cross-process trust state synchronization.

    Implementations write circuit breaker state to a shared store (Redis)
    so the Go Execution Envelope can enforce trust decisions at O(1) cost.
    """

    def publish_state(
        self,
        agent_id: str,
        state: CircuitState,
        *,
        trust_score: float = 0.0,
        pair_id: str = "",
    ) -> None:
        """Publish circuit breaker state transition.

        Args:
            agent_id: The agent whose state changed.
            state: New circuit state (TRUSTED/EVALUATING/ISOLATED/TERMINATED).
            trust_score: Current trust score for telemetry.
            pair_id: Agent pair identifier for telemetry.
        """
        ...

    def close(self) -> None:
        """Release resources (connections, threads)."""
        ...


class NullBridge:
    """No-op bridge for when IPC is not configured."""

    def publish_state(
        self,
        agent_id: str,
        state: CircuitState,
        *,
        trust_score: float = 0.0,
        pair_id: str = "",
    ) -> None:
        pass

    def close(self) -> None:
        pass
