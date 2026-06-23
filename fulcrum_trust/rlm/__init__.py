"""Long-context navigation prototype (RLM) — **public but unstable**.

.. warning::

    This subpackage is a **Phase 5 prototype**. It is published for benchmark
    transparency and architecture discussion, **not** as a stable API: every
    symbol exported here may change or be removed without notice, and it is
    **not production-stable**. The restricted runtime is intentionally minimal
    and is **not a security boundary** (see ``SECURITY.md``) — do not use it to
    execute untrusted navigation programs. See ``docs/rlm-python-prototype.md``
    for status and benchmark methodology, and ``PUNCH_LIST.md`` (PL-3) for the
    decision to keep this surface explicitly unstable.

The trust-scoring core (``fulcrum_trust.evaluator`` / ``manager`` / ``decay`` /
``types``) does not depend on anything in this package — ``rlm`` is a
self-contained leaf, so its prototype status does not affect the stability of
the core trust contract.
"""

from __future__ import annotations

from fulcrum_trust.rlm.context import (
    DEFAULT_PARTITION_TOKENS,
    DEFAULT_TOKEN_BUDGET,
    externalize_context,
)
from fulcrum_trust.rlm.fixtures import (
    GRATITUDE_PHRASES,
    SyntheticSessionFixture,
    build_neutral_history,
    generate_gratitude_loop_fixture,
)
from fulcrum_trust.rlm.prototype import (
    DEFAULT_OBJECTIVE,
    RLMPrototype,
    StandardRecallBaseline,
    score_gratitude_signal,
)
from fulcrum_trust.rlm.types import (
    BatchFinding,
    BenchmarkCase,
    ContextExhausted,
    ContextPartition,
    ExternalizedContext,
    PrototypeResult,
    RecallBenchmarkResult,
    RuntimeTrace,
)

__all__ = [
    "BatchFinding",
    "BenchmarkCase",
    "ContextExhausted",
    "ContextPartition",
    "DEFAULT_OBJECTIVE",
    "DEFAULT_PARTITION_TOKENS",
    "DEFAULT_TOKEN_BUDGET",
    "ExternalizedContext",
    "GRATITUDE_PHRASES",
    "PrototypeResult",
    "RLMPrototype",
    "RecallBenchmarkResult",
    "RuntimeTrace",
    "StandardRecallBaseline",
    "SyntheticSessionFixture",
    "build_neutral_history",
    "externalize_context",
    "generate_gratitude_loop_fixture",
    "score_gratitude_signal",
]

# Machine-readable stability marker for this subpackage. ``rlm`` is a public but
# unstable Phase 5 prototype — see the module docstring above and PUNCH_LIST.md
# (PL-3). Not part of the stable public contract; may change without notice.
__stability__ = "prototype"
