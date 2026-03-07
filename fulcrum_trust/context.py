from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass


@dataclass
class TrustEvaluationContext:
    """Metadata for the currently active trust evaluation.

    Stored in a ContextVar so concurrent asyncio tasks or threads
    each maintain independent context without cross-contamination.
    """

    pair_id: str


# Module-level ContextVar. Default is None (no active evaluation).
_trust_context: ContextVar[TrustEvaluationContext | None] = ContextVar(
    "_trust_context", default=None
)


def get_current_context() -> TrustEvaluationContext | None:
    """Return the active TrustEvaluationContext, or None if not set."""
    return _trust_context.get()


def set_trust_context(pair_id: str) -> object:
    """Set the active context and return a Token for restoration.

    Usage::

        token = set_trust_context("agent_a|agent_b")
        try:
            ...
        finally:
            reset_trust_context(token)
    """
    return _trust_context.set(TrustEvaluationContext(pair_id=pair_id))


def reset_trust_context(token: object) -> None:
    """Restore the context to its state before set_trust_context was called."""
    _trust_context.reset(token)  # type: ignore[arg-type]
