from __future__ import annotations
from fulcrum_trust.types import TrustState


class MemoryStore:
    """In-memory trust state store. Not thread-safe. Default store for TrustManager."""

    def __init__(self) -> None:
        self._data: dict[str, TrustState] = {}

    def get(self, pair_id: str) -> TrustState | None:
        """Return TrustState for pair_id, or None if not found."""
        return self._data.get(pair_id)

    def put(self, pair_id: str, state: TrustState) -> None:
        """Persist state for pair_id, overwriting any existing entry."""
        self._data[pair_id] = state

    def delete(self, pair_id: str) -> None:
        """Remove pair_id from store. No-op if not found."""
        self._data.pop(pair_id, None)

    def all_pairs(self) -> list[str]:
        """Return all known pair_ids."""
        return list(self._data.keys())
