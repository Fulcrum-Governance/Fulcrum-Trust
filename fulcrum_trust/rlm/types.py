from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


class ContextExhausted(Exception):
    """Raised when externalized context exceeds the configured token budget."""

    def __init__(self, token_count: int, token_budget: int) -> None:
        self.token_count = token_count
        self.token_budget = token_budget
        super().__init__(
            f"Context exhausted: {token_count} tokens exceeds budget {token_budget}"
        )


@dataclass(frozen=True)
class ContextPartition:
    """A single externalized partition addressable by symbolic handle."""

    handle: str
    index: int
    token_start: int
    token_end: int
    token_count: int
    content: str


@dataclass(frozen=True)
class ExternalizedContext:
    """Partitioned long-context state exposed through symbolic handles."""

    session_id: str
    partitions: tuple[ContextPartition, ...]
    total_tokens: int
    token_budget: int

    @property
    def handles(self) -> tuple[str, ...]:
        """Return the symbolic handles in partition order."""
        return tuple(partition.handle for partition in self.partitions)

    def middle_handles(self) -> tuple[str, ...]:
        """Return handles covering the middle 80% of the context."""
        partition_count = len(self.partitions)
        if partition_count <= 2:
            return self.handles

        start = max(0, int(partition_count * 0.1))
        end = max(start + 1, int(partition_count * 0.9))
        return tuple(partition.handle for partition in self.partitions[start:end])


@dataclass(frozen=True)
class BatchFinding:
    """A scored result returned by the prototype's llm_batch simulation."""

    handle: str
    score: float
    excerpt: str
    matches: tuple[str, ...]


@dataclass(frozen=True)
class RuntimeTrace:
    """Captured state from a single navigation-program execution."""

    answer: Mapping[str, object]
    analysis_steps: tuple[str, ...]
    inspected_handles: tuple[str, ...]
    evidence: tuple[BatchFinding, ...]


@dataclass(frozen=True)
class PrototypeResult:
    """End-to-end output of the RLM prototype."""

    answer: Mapping[str, object]
    report: str
    tool_chain: tuple[str, ...]
    total_tokens: int
    total_partitions: int
    program: str
    analysis_steps: tuple[str, ...]
    inspected_handles: tuple[str, ...]
    evidence: tuple[BatchFinding, ...]
    baseline_detected: bool
    prototype_detected: bool


@dataclass(frozen=True)
class BenchmarkCase:
    """One recall-benchmark observation for a planted signal position."""

    pattern_position: float
    total_tokens: int
    baseline_detected: bool
    prototype_detected: bool


@dataclass(frozen=True)
class RecallBenchmarkResult:
    """Summary metrics comparing the prototype with the baseline."""

    fixture_count: int
    prototype_hits: int
    baseline_hits: int
    prototype_accuracy: float
    baseline_accuracy: float
    cases: tuple[BenchmarkCase, ...]
