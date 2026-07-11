from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum


class TrustOutcome(str, Enum):
    """Outcome of an agent-to-agent interaction."""

    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"


class TrustCircuitOpen(Exception):
    """Raised when trust drops below threshold and raise_on_break=True.

    Attributes:
        pair_id: Canonical pair identifier (sorted agent IDs joined by '|').
        trust_score: Current trust score at time of circuit break.
        threshold: Configured threshold that was violated.
    """

    def __init__(self, pair_id: str, trust_score: float, threshold: float) -> None:
        self.pair_id = pair_id
        self.trust_score = trust_score
        self.threshold = threshold
        super().__init__(
            f"Trust circuit open for pair '{pair_id}': "
            f"score {trust_score:.3f} < threshold {threshold:.3f}"
        )


@dataclass
class TrustState:
    """Mutable Beta(alpha, beta) trust state for an agent pair."""

    pair_id: str
    agent_a: str
    agent_b: str
    alpha: float = 1.0  # successes; prior=1.0 (uninformative)
    beta_val: float = 1.0  # failures; prior=1.0 (uninformative)
    last_updated: float = field(default_factory=time.time)
    interaction_count: int = 0
    circuit_state: str = (
        "CLOSED"  # CircuitBreakerState: CLOSED | OPEN | HALF_OPEN | TERMINATED
    )
    opened_at: float | None = None  # wall-clock time the pair entered OPEN;
    # None until first OPEN (and for pre-opened_at persisted state). Anchors the
    # recovery cooldown gate — see TrustConfig.recovery_cooldown_seconds.

    @property
    def trust_score(self) -> float:
        """Beta distribution mean: alpha / (alpha + beta_val)."""
        return self.alpha / (self.alpha + self.beta_val)


@dataclass
class TrustConfig:
    """Configuration for the trust engine.

    Args:
        threshold: Circuit break threshold. Trust below this triggers termination.
            Default 0.3.
        half_life_seconds: Half-life for exponential decay. Default 86400 (24 hours).
        alpha_prior: Initial alpha for new pairs. Default 1.0 (uninformative prior).
        beta_prior: Initial beta for new pairs. Default 1.0 (uninformative prior).
        success_weight: Alpha increment per SUCCESS outcome. Default 1.0.
        failure_weight: Beta increment per FAILURE outcome. Default 1.0.
        partial_alpha_weight: Alpha increment per PARTIAL outcome. Default 0.5.
        partial_beta_weight: Beta increment per PARTIAL outcome. Default 0.5.
        recovery_cooldown_seconds: If set (> 0), recovery from OPEN routes through
            a HALF_OPEN probe rather than jumping straight to CLOSED: the pair
            stays OPEN until this many seconds elapse since it entered OPEN, then
            the next evaluation admits a HALF_OPEN probe whose outcome resolves to
            CLOSED (recovered) or OPEN (still failing). Default ``None`` preserves
            the direct OPEN -> CLOSED recovery edge (zero behavior change).
    """

    threshold: float = 0.3
    half_life_seconds: float = 86400.0
    alpha_prior: float = 1.0
    beta_prior: float = 1.0
    success_weight: float = 1.0
    failure_weight: float = 1.0
    partial_alpha_weight: float = 0.5
    partial_beta_weight: float = 0.5
    recovery_cooldown_seconds: float | None = None

    def __post_init__(self) -> None:
        if not 0.0 < self.threshold < 1.0:
            raise ValueError(f"threshold must be in (0, 1), got {self.threshold}")
        if self.half_life_seconds <= 0:
            raise ValueError(
                f"half_life_seconds must be positive, got {self.half_life_seconds}"
            )
        if (
            self.recovery_cooldown_seconds is not None
            and self.recovery_cooldown_seconds <= 0
        ):
            raise ValueError(
                "recovery_cooldown_seconds must be positive when set, "
                f"got {self.recovery_cooldown_seconds}"
            )
