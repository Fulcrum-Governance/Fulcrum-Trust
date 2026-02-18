from __future__ import annotations
from typing import Protocol, runtime_checkable
from fulcrum_trust.types import TrustState


@runtime_checkable
class TrustStore(Protocol):
    """Interface for trust state persistence.

    Any class implementing get/put/delete/all_pairs satisfies this Protocol
    without inheriting from it (structural subtyping).
    """

    def get(self, pair_id: str) -> TrustState | None:
        """Return TrustState for pair_id, or None if not found."""
        ...

    def put(self, pair_id: str, state: TrustState) -> None:
        """Persist state for pair_id, overwriting any existing entry."""
        ...

    def delete(self, pair_id: str) -> None:
        """Remove pair_id from store. No-op if not found."""
        ...

    def all_pairs(self) -> list[str]:
        """Return all known pair_ids."""
        ...
