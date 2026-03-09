from __future__ import annotations

from fulcrum_trust.rlm.types import (
    ContextExhausted,
    ContextPartition,
    ExternalizedContext,
)

DEFAULT_PARTITION_TOKENS = 2048
DEFAULT_TOKEN_BUDGET = 128_000


def count_tokens(text: str) -> int:
    """Return a lightweight token estimate using whitespace segmentation."""
    return len(text.split())


def externalize_context(
    session_history: str,
    *,
    session_id: str = "session",
    partition_tokens: int = DEFAULT_PARTITION_TOKENS,
    token_budget: int = DEFAULT_TOKEN_BUDGET,
) -> ExternalizedContext:
    """Partition a long session history into symbolic-handle slices."""
    if partition_tokens <= 0:
        raise ValueError("partition_tokens must be positive")
    if token_budget <= 0:
        raise ValueError("token_budget must be positive")

    tokens = session_history.split()
    total_tokens = len(tokens)
    if total_tokens > token_budget:
        raise ContextExhausted(total_tokens, token_budget)

    partitions: list[ContextPartition] = []
    for index, start in enumerate(range(0, total_tokens, partition_tokens)):
        chunk_tokens = tokens[start : start + partition_tokens]
        handle = f"ctx://{session_id}/{index:04d}"
        partitions.append(
            ContextPartition(
                handle=handle,
                index=index,
                token_start=start,
                token_end=start + len(chunk_tokens),
                token_count=len(chunk_tokens),
                content=" ".join(chunk_tokens),
            )
        )

    return ExternalizedContext(
        session_id=session_id,
        partitions=tuple(partitions),
        total_tokens=total_tokens,
        token_budget=token_budget,
    )
