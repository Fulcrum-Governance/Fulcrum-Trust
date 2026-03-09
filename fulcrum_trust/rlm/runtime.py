from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from fulcrum_trust.rlm.types import BatchFinding, ExternalizedContext, RuntimeTrace

Detector = Callable[[str], tuple[float, tuple[str, ...]]]


class RLMRuntime:
    """Restricted REPL-style runtime for handle-based context navigation."""

    def __init__(
        self,
        context: ExternalizedContext,
        *,
        max_workers: int = 4,
        detection_threshold: float = 6.0,
    ) -> None:
        self._context = context
        self._max_workers = max_workers
        self._detection_threshold = detection_threshold
        self._partitions = {
            partition.handle: partition for partition in context.partitions
        }
        self._answer: dict[str, object] = {"content": "", "ready": False}
        self._analysis_steps: list[str] = []
        self._inspected_handles: list[str] = []
        self._evidence: list[BatchFinding] = []

    def execute(
        self, program: str, *, objective: str, detector: Detector
    ) -> RuntimeTrace:
        """Execute a generated navigation program against the externalized context."""
        safe_builtins: dict[str, object] = {
            "dict": dict,
            "enumerate": enumerate,
            "len": len,
            "list": list,
            "max": max,
            "min": min,
            "range": range,
            "sorted": sorted,
            "sum": sum,
            "tuple": tuple,
        }
        namespace: dict[str, object] = {
            "__builtins__": safe_builtins,
            "answer": self._answer,
            "detection_threshold": self._detection_threshold,
            "llm_batch": lambda handles, objective_text=objective: self.llm_batch(
                handles,
                objective=objective_text,
                detector=detector,
            ),
            "middle_handles": self._context.middle_handles,
            "objective": objective,
            "peek": self.peek,
            "record_step": self.record_step,
            "update_answer": self.update_answer,
        }
        exec(program, namespace, namespace)
        return RuntimeTrace(
            answer=dict(self._answer),
            analysis_steps=tuple(self._analysis_steps),
            inspected_handles=tuple(self._inspected_handles),
            evidence=tuple(self._evidence),
        )

    def record_step(self, name: str) -> None:
        """Append a named analysis step to the runtime trace."""
        self._analysis_steps.append(name)

    def peek(self, handle: str, *, radius: int = 0) -> str:
        """Read one handle, optionally widening to neighboring partitions."""
        partition = self._partitions[handle]
        start = max(0, partition.index - radius)
        end = min(len(self._context.partitions), partition.index + radius + 1)
        selected = self._context.partitions[start:end]
        self._inspected_handles.extend(item.handle for item in selected)
        return "\n".join(item.content for item in selected)

    def llm_batch(
        self,
        handles: Sequence[str],
        *,
        objective: str,
        detector: Detector,
    ) -> list[BatchFinding]:
        """Score candidate handles in parallel using a deterministic detector."""
        del objective
        candidate_handles = tuple(handles)
        if not candidate_handles:
            return []

        worker_count = max(1, min(self._max_workers, len(candidate_handles)))
        with ThreadPoolExecutor(max_workers=worker_count) as pool:
            findings = list(
                pool.map(
                    lambda handle: self._score_handle(handle, detector),
                    candidate_handles,
                )
            )

        filtered = [finding for finding in findings if finding.score > 0.0]
        filtered.sort(key=lambda finding: finding.score, reverse=True)
        return filtered

    def update_answer(
        self,
        *,
        content: str,
        evidence: Sequence[BatchFinding],
        ready: bool,
    ) -> None:
        """Update the mutable answer state exposed inside the runtime."""
        evidence_tuple = tuple(evidence)
        self._evidence = list(evidence_tuple)
        self._answer["content"] = content
        self._answer["ready"] = ready
        self._answer["evidence_handles"] = tuple(item.handle for item in evidence_tuple)
        self._answer["matches"] = tuple(
            match for item in evidence_tuple for match in item.matches
        )

    def _score_handle(self, handle: str, detector: Detector) -> BatchFinding:
        partition = self._partitions[handle]
        score, matches = detector(partition.content)
        excerpt = " ".join(partition.content.split()[:40])
        return BatchFinding(
            handle=handle,
            score=score,
            excerpt=excerpt,
            matches=matches,
        )
