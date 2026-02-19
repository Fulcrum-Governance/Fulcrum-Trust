from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum


class TrustOutcome(str, Enum):
    """Outcome of an agent-to-agent interaction."""

    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"


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
    """

    threshold: float = 0.3
    half_life_seconds: float = 86400.0
    alpha_prior: float = 1.0
    beta_prior: float = 1.0
    success_weight: float = 1.0
    failure_weight: float = 1.0
    partial_alpha_weight: float = 0.5
    partial_beta_weight: float = 0.5

    def __post_init__(self) -> None:
        if not 0.0 < self.threshold < 1.0:
            raise ValueError(f"threshold must be in (0, 1), got {self.threshold}")
        if self.half_life_seconds <= 0:
            raise ValueError(
                f"half_life_seconds must be positive, got {self.half_life_seconds}"
            )
