from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from fulcrum_trust.rlm.context import count_tokens

GRATITUDE_PHRASES = (
    "thank you",
    "thanks again",
    "appreciate your help",
    "grateful for the handoff",
    "happy to help",
    "you are welcome",
)


@dataclass(frozen=True)
class SyntheticSessionFixture:
    """A deterministic long-context session used for Phase 5 benchmarking."""

    history: str
    total_tokens: int
    pattern_position: float
    expected_phrases: tuple[str, ...]


def _neutral_line(index: int) -> str:
    speaker = "orchestrator" if index % 2 == 0 else "worker"
    return (
        f"{speaker} reviews workflow item {index} and records stable execution "
        "evidence for audit continuity"
    )


def _gratitude_loop_lines(repetitions: int) -> list[str]:
    lines: list[str] = []
    for index in range(repetitions):
        lines.append(
            "orchestrator says thank you and appreciate your help while requesting "
            f"another confirmation cycle {index}"
        )
        lines.append(
            "worker replies thanks again and grateful for the handoff while saying "
            f"you are welcome and happy to help on loop {index}"
        )
    return lines


def _build_neutral_lines(target_tokens: int) -> list[str]:
    lines: list[str] = []
    token_total = 0
    index = 0
    while token_total < target_tokens:
        line = _neutral_line(index)
        lines.append(line)
        token_total += count_tokens(line)
        index += 1
    return lines


@lru_cache(maxsize=16)
def build_neutral_history(target_tokens: int) -> str:
    """Return a deterministic neutral session with approximately target_tokens."""
    if target_tokens <= 0:
        raise ValueError("target_tokens must be positive")

    lines = _build_neutral_lines(target_tokens)
    history = "\n".join(lines)
    tokens = history.split()
    return " ".join(tokens[:target_tokens])


@lru_cache(maxsize=32)
def generate_gratitude_loop_fixture(
    *,
    target_tokens: int = 110_000,
    pattern_position: float = 0.55,
    repetitions: int = 24,
) -> SyntheticSessionFixture:
    """Return a 100K+-token session with a gratitude loop planted in the middle band."""
    if not 0.1 <= pattern_position <= 0.9:
        raise ValueError("pattern_position must be within the middle 80% of context")

    loop_lines = _gratitude_loop_lines(repetitions)
    loop_tokens = sum(count_tokens(line) for line in loop_lines)
    if loop_tokens >= target_tokens:
        raise ValueError("loop payload must be smaller than target_tokens")

    background_target = target_tokens - loop_tokens
    background = _build_neutral_lines(background_target)

    insert_at = min(len(background), max(1, int(len(background) * pattern_position)))
    lines = background[:insert_at] + loop_lines + background[insert_at:]
    history = "\n".join(lines)
    tokens = history.split()
    trimmed_history = " ".join(tokens[:target_tokens])

    return SyntheticSessionFixture(
        history=trimmed_history,
        total_tokens=count_tokens(trimmed_history),
        pattern_position=pattern_position,
        expected_phrases=GRATITUDE_PHRASES,
    )
