from __future__ import annotations

import pytest

from fulcrum_trust.rlm import (
    ContextExhausted,
    build_neutral_history,
    externalize_context,
)
from fulcrum_trust.rlm.fixtures import generate_gratitude_loop_fixture


def test_externalize_context_processes_100k_fixture_without_truncation() -> None:
    fixture = generate_gratitude_loop_fixture(
        target_tokens=110_000, pattern_position=0.55
    )

    context = externalize_context(fixture.history, session_id="fixture")

    assert context.total_tokens >= 100_000
    assert context.total_tokens == fixture.total_tokens
    assert len(context.partitions) > 1
    assert context.handles[0] == "ctx://fixture/0000"
    assert (
        sum(partition.token_count for partition in context.partitions)
        == fixture.total_tokens
    )


def test_externalize_context_raises_context_exhausted_over_budget() -> None:
    oversized_history = build_neutral_history(128_500)

    with pytest.raises(ContextExhausted) as excinfo:
        externalize_context(oversized_history, token_budget=128_000)

    assert excinfo.value.token_count > excinfo.value.token_budget


def test_externalize_context_rejects_nonpositive_partition_tokens() -> None:
    with pytest.raises(ValueError, match="partition_tokens must be positive"):
        externalize_context("a b c", partition_tokens=0)


def test_externalize_context_rejects_nonpositive_token_budget() -> None:
    with pytest.raises(ValueError, match="token_budget must be positive"):
        externalize_context("a b c", token_budget=0)


def test_middle_handles_returns_all_for_small_context() -> None:
    """With two or fewer partitions there is no middle band to trim to."""
    context = externalize_context("alpha beta gamma delta", partition_tokens=2048)

    assert len(context.partitions) == 1
    assert context.middle_handles() == context.handles
