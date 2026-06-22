from __future__ import annotations

import pytest

from fulcrum_trust.rlm.fixtures import (
    build_neutral_history,
    generate_gratitude_loop_fixture,
)


def test_build_neutral_history_rejects_nonpositive_target() -> None:
    """target_tokens must be positive (fixtures.py guard)."""
    with pytest.raises(ValueError, match="target_tokens must be positive"):
        build_neutral_history(0)
    with pytest.raises(ValueError, match="target_tokens must be positive"):
        build_neutral_history(-100)


def test_generate_fixture_rejects_position_outside_middle_band() -> None:
    """pattern_position must sit within the middle 80% of context."""
    with pytest.raises(
        ValueError, match="pattern_position must be within the middle 80%"
    ):
        generate_gratitude_loop_fixture(target_tokens=5000, pattern_position=0.05)
    with pytest.raises(
        ValueError, match="pattern_position must be within the middle 80%"
    ):
        generate_gratitude_loop_fixture(target_tokens=5000, pattern_position=0.95)


def test_generate_fixture_rejects_loop_larger_than_target() -> None:
    """When the gratitude loop payload would not fit, construction fails loudly."""
    # repetitions=24 yields ~840 loop tokens, which cannot fit in 100 target tokens.
    with pytest.raises(
        ValueError, match="loop payload must be smaller than target_tokens"
    ):
        generate_gratitude_loop_fixture(target_tokens=100, pattern_position=0.5)
