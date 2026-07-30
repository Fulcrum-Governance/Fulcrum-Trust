"""Supply-chain guard: the publish action must stay pinned to a commit SHA.

``pypa/gh-action-pypi-publish`` is the one action in this repository that holds an
OIDC credential. It floated on the mutable ``release/v1`` branch until FUL-369.
Nothing but reviewer attention stops a future edit from putting a mutable ref
back, so assert the pin here instead.

Deliberately stdlib-only — a regex over the raw workflow text, no YAML parser —
so the guard adds no dependency to a package whose runtime dependency list is
empty by design.
"""

from __future__ import annotations

import pathlib
import re

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
PUBLISH_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "publish.yml"

# Captures the ref and any trailing comment for every use of the publish action:
#   - uses: pypa/gh-action-pypi-publish@<ref> # <comment>
PUBLISH_ACTION_USE = re.compile(
    r"^\s*-\s*uses:\s*pypa/gh-action-pypi-publish@(?P<ref>\S+)(?P<comment>.*)$",
    re.MULTILINE,
)

COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")
VERSION_COMMENT = re.compile(r"#\s*v\d+\.\d+\.\d+")


def _uses() -> list[re.Match[str]]:
    return list(PUBLISH_ACTION_USE.finditer(PUBLISH_WORKFLOW.read_text()))


def test_publish_action_used_at_both_steps() -> None:
    """TestPyPI and PyPI each invoke the action — exactly two uses, no more."""
    assert len(_uses()) == 2, (
        "expected pypa/gh-action-pypi-publish at exactly 2 steps "
        f"(TestPyPI + PyPI), found {len(_uses())}"
    )


def test_publish_action_pinned_to_commit_sha() -> None:
    """Every use pins a 40-hex commit, never a tag or a branch like release/v1."""
    for match in _uses():
        ref = match.group("ref")
        assert COMMIT_SHA.match(ref), (
            f"pypa/gh-action-pypi-publish is pinned to {ref!r}, which is not a "
            "40-character commit SHA. Tags and branches are mutable; resolve the "
            "release tag to its commit and pin that."
        )


def test_publish_action_pins_agree() -> None:
    """Both steps run the same commit — the pins can never drift apart."""
    refs = {match.group("ref") for match in _uses()}
    assert len(refs) == 1, (
        f"the TestPyPI and PyPI steps pin different commits: {sorted(refs)}. "
        "A TestPyPI gate only guards prod if both steps run the same code."
    )


def test_publish_action_pin_names_its_version() -> None:
    """A bare SHA is unreadable; each pin carries a `# vX.Y.Z` comment."""
    for match in _uses():
        comment = match.group("comment")
        assert VERSION_COMMENT.search(comment), (
            f"the pin {match.group('ref')!r} has no '# vX.Y.Z' comment. Without it "
            "no reviewer can tell which release the SHA represents."
        )
