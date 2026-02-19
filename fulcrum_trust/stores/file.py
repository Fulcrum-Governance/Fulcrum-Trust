from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from fulcrum_trust.types import TrustState


class FileStore:
    """JSON file-backed trust state store. Saves on every write (v0.1.0 simplicity).

    Warning: Not atomic — concurrent writes or interrupted saves may corrupt data.
    Not thread-safe.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._data: dict[str, dict[str, object]] = {}
        if self._path.exists():
            self._load()

    def _load(self) -> None:
        with self._path.open() as f:
            content = f.read().strip()
        if not content:
            self._data = {}
            return
        self._data = json.loads(content)

    def _save(self) -> None:
        with self._path.open("w") as f:
            json.dump(self._data, f, indent=2)

    def get(self, pair_id: str) -> TrustState | None:
        """Return TrustState for pair_id, or None if not found."""
        raw = self._data.get(pair_id)
        if raw is None:
            return None
        return TrustState(**raw)  # type: ignore[arg-type]

    def put(self, pair_id: str, state: TrustState) -> None:
        """Persist state for pair_id, overwriting any existing entry."""
        self._data[pair_id] = asdict(state)
        self._save()

    def delete(self, pair_id: str) -> None:
        """Remove pair_id from store. No-op if not found."""
        self._data.pop(pair_id, None)
        self._save()

    def all_pairs(self) -> list[str]:
        """Return all known pair_ids."""
        return list(self._data.keys())
