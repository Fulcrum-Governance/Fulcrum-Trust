from __future__ import annotations

from collections.abc import Mapping, Sequence

from fulcrum_trust.rlm.context import (
    DEFAULT_PARTITION_TOKENS,
    DEFAULT_TOKEN_BUDGET,
    externalize_context,
)
from fulcrum_trust.rlm.fixtures import (
    GRATITUDE_PHRASES,
    generate_gratitude_loop_fixture,
)
from fulcrum_trust.rlm.runtime import RLMRuntime
from fulcrum_trust.rlm.types import (
    BatchFinding,
    BenchmarkCase,
    PrototypeResult,
    RecallBenchmarkResult,
)

DEFAULT_OBJECTIVE = (
    "Inspect the externalized session for a runaway gratitude loop hidden in the "
    "middle of the conversation."
)


def score_gratitude_signal(text: str) -> tuple[float, tuple[str, ...]]:
    """Score a text block for gratitude-loop characteristics."""
    normalized = text.lower()
    score = 0.0
    matches: list[str] = []
    weights = {
        "thank you": 2.0,
        "thanks again": 1.5,
        "appreciate your help": 1.5,
        "grateful for the handoff": 1.5,
        "happy to help": 1.0,
        "you are welcome": 1.0,
    }
    for phrase in GRATITUDE_PHRASES:
        count = normalized.count(phrase)
        if count:
            score += count * weights[phrase]
            matches.extend([phrase] * count)
    if score > 0 and "orchestrator" in normalized and "worker" in normalized:
        score += 1.0
    return score, tuple(dict.fromkeys(matches))


class StandardRecallBaseline:
    """Simple head-tail baseline that approximates lost-in-the-middle failure."""

    def __init__(self, window_tokens: int = 4096, threshold: float = 6.0) -> None:
        self._window_tokens = window_tokens
        self._threshold = threshold

    def detect(self, session_history: str) -> bool:
        """Inspect only the leading and trailing windows of a long session."""
        tokens = session_history.split()
        visible = tokens[: self._window_tokens] + tokens[-self._window_tokens :]
        score, _ = score_gratitude_signal(" ".join(visible))
        return score >= self._threshold


class RLMPrototype:
    """Minimal Python-side prototype for governed long-context navigation.

    .. warning::

        ``RLMPrototype`` is a Phase 5 prototype — **public but unstable** and
        **not production-stable**. The API may change without notice, and the
        restricted execution engine is intentionally minimal (the future
        production runtime is expected to swap in a hardened sandbox). See
        ``docs/rlm-python-prototype.md`` for status.
    """

    def __init__(
        self,
        *,
        token_budget: int = DEFAULT_TOKEN_BUDGET,
        partition_tokens: int = DEFAULT_PARTITION_TOKENS,
        detection_threshold: float = 6.0,
        batch_workers: int = 4,
        baseline: StandardRecallBaseline | None = None,
    ) -> None:
        self._token_budget = token_budget
        self._partition_tokens = partition_tokens
        self._detection_threshold = detection_threshold
        self._batch_workers = batch_workers
        self._baseline = baseline if baseline is not None else StandardRecallBaseline()

    def build_navigation_program(self) -> str:
        """Return the deterministic navigation program executed by the runtime."""
        return "\n".join(
            (
                "record_step('sample-middle-band')",
                "candidate_handles = middle_handles()",
                "record_step('batch-score-handles')",
                "findings = llm_batch(candidate_handles)",
                "focus_handles = [finding.handle for finding in findings[:3]]",
                "snippets = [peek(handle, radius=1) for handle in focus_handles]",
                "record_step('mutate-answer')",
                "if findings and findings[0].score >= detection_threshold:",
                "    update_answer(",
                "        content=(",
                "            f'Detected gratitude loop in {findings[0].handle} '",
                "            f'with score {findings[0].score:.1f}.'",
                "        ),",
                "        evidence=findings[:3],",
                "        ready=True,",
                "    )",
                "else:",
                "    update_answer(",
                "        content='No gratitude loop detected.',",
                "        evidence=findings[:1],",
                "        ready=False,",
                "    )",
            )
        )

    def analyze(
        self,
        session_history: str,
        *,
        session_id: str = "gratitude-loop",
        objective: str = DEFAULT_OBJECTIVE,
    ) -> PrototypeResult:
        """Run the read → analyze → report tool chain over a long session."""
        context = externalize_context(
            session_history,
            session_id=session_id,
            partition_tokens=self._partition_tokens,
            token_budget=self._token_budget,
        )
        runtime = RLMRuntime(
            context,
            max_workers=self._batch_workers,
            detection_threshold=self._detection_threshold,
        )
        program = self.build_navigation_program()
        trace = runtime.execute(
            program,
            objective=objective,
            detector=score_gratitude_signal,
        )
        prototype_detected = bool(trace.answer.get("ready", False))
        baseline_detected = self._baseline.detect(session_history)
        report = self._render_report(trace.answer, trace.evidence)

        return PrototypeResult(
            answer=trace.answer,
            report=report,
            tool_chain=("read", "analyze", "report"),
            total_tokens=context.total_tokens,
            total_partitions=len(context.partitions),
            program=program,
            analysis_steps=trace.analysis_steps,
            inspected_handles=trace.inspected_handles,
            evidence=trace.evidence,
            baseline_detected=baseline_detected,
            prototype_detected=prototype_detected,
        )

    def benchmark_middle_position_recall(
        self,
        *,
        positions: Sequence[float] = (0.2, 0.35, 0.5, 0.65, 0.8),
        target_tokens: int = 110_000,
    ) -> RecallBenchmarkResult:
        """Compare prototype recall against the baseline across middle positions."""
        cases: list[BenchmarkCase] = []
        prototype_hits = 0
        baseline_hits = 0
        for position in positions:
            fixture = generate_gratitude_loop_fixture(
                target_tokens=target_tokens,
                pattern_position=position,
            )
            result = self.analyze(
                fixture.history,
                session_id=f"benchmark-{int(position * 100):02d}",
            )
            prototype_hits += int(result.prototype_detected)
            baseline_hits += int(result.baseline_detected)
            cases.append(
                BenchmarkCase(
                    pattern_position=position,
                    total_tokens=fixture.total_tokens,
                    baseline_detected=result.baseline_detected,
                    prototype_detected=result.prototype_detected,
                )
            )

        fixture_count = len(cases)
        return RecallBenchmarkResult(
            fixture_count=fixture_count,
            prototype_hits=prototype_hits,
            baseline_hits=baseline_hits,
            prototype_accuracy=prototype_hits / fixture_count,
            baseline_accuracy=baseline_hits / fixture_count,
            cases=tuple(cases),
        )

    def _render_report(
        self,
        answer: Mapping[str, object],
        evidence: tuple[BatchFinding, ...],
    ) -> str:
        content = str(answer.get("content", ""))
        evidence_value = answer.get("evidence_handles", ())
        if isinstance(evidence_value, tuple):
            evidence_handles = evidence_value
        elif isinstance(evidence_value, list):
            evidence_handles = tuple(evidence_value)
        else:
            evidence_handles = ()
        handle_list = ", ".join(str(handle) for handle in evidence_handles)
        if evidence and handle_list:
            return f"{content} Evidence handles: {handle_list}."
        return content
