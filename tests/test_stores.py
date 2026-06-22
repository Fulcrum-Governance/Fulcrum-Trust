from __future__ import annotations

import pytest

from fulcrum_trust.stores.base import TrustStore
from fulcrum_trust.stores.file import FileStore
from fulcrum_trust.stores.memory import MemoryStore
from fulcrum_trust.types import TrustState


def _make_state(pair_id: str = "abc123") -> TrustState:
    return TrustState(
        pair_id=pair_id,
        agent_a="agent-a",
        agent_b="agent-b",
        alpha=2.0,
        beta_val=1.0,
        interaction_count=1,
    )


class TestMemoryStore:
    def test_get_unknown_pair_returns_none(self) -> None:
        store = MemoryStore()
        assert store.get("unknown") is None

    def test_put_then_get(self) -> None:
        store = MemoryStore()
        state = _make_state()
        store.put(state.pair_id, state)
        result = store.get(state.pair_id)
        assert result is state

    def test_delete_existing(self) -> None:
        store = MemoryStore()
        state = _make_state()
        store.put(state.pair_id, state)
        store.delete(state.pair_id)
        assert store.get(state.pair_id) is None

    def test_delete_nonexistent_noop(self) -> None:
        store = MemoryStore()
        store.delete("nonexistent")  # Should not raise

    def test_all_pairs_empty(self) -> None:
        store = MemoryStore()
        assert store.all_pairs() == []

    def test_all_pairs_returns_ids(self) -> None:
        store = MemoryStore()
        store.put("pair-1", _make_state("pair-1"))
        store.put("pair-2", _make_state("pair-2"))
        assert set(store.all_pairs()) == {"pair-1", "pair-2"}

    def test_overwrite_on_put(self) -> None:
        store = MemoryStore()
        state1 = _make_state()
        state1.alpha = 2.0
        store.put(state1.pair_id, state1)
        state2 = _make_state()
        state2.alpha = 5.0
        store.put(state2.pair_id, state2)
        result = store.get(state1.pair_id)
        assert result is not None
        assert result.alpha == pytest.approx(5.0)

    def test_satisfies_protocol(self) -> None:
        """MemoryStore satisfies TrustStore Protocol at runtime."""
        store = MemoryStore()
        assert isinstance(store, TrustStore)


class TestFileStore:
    def test_get_unknown_pair_returns_none(
        self, tmp_path: pytest.TempPathFactory
    ) -> None:
        store = FileStore(tmp_path / "trust.json")
        assert store.get("unknown") is None

    def test_put_then_get_same_instance(self, tmp_path: pytest.TempPathFactory) -> None:
        store = FileStore(tmp_path / "trust.json")
        state = _make_state()
        store.put(state.pair_id, state)
        result = store.get(state.pair_id)
        assert result is not None
        assert result.pair_id == state.pair_id
        assert result.alpha == pytest.approx(state.alpha)
        assert result.beta_val == pytest.approx(state.beta_val)

    def test_round_trip_fresh_instance(self, tmp_path: pytest.TempPathFactory) -> None:
        """FileStore persists across TrustManager sessions (TRUST-06)."""
        path = tmp_path / "trust.json"
        state = _make_state()
        # Write with first instance
        store1 = FileStore(path)
        store1.put(state.pair_id, state)
        # Read with fresh instance (simulates new process)
        store2 = FileStore(path)
        result = store2.get(state.pair_id)
        assert result is not None
        assert result.pair_id == state.pair_id
        assert result.alpha == pytest.approx(state.alpha)
        assert result.interaction_count == state.interaction_count

    def test_delete_then_get_none(self, tmp_path: pytest.TempPathFactory) -> None:
        store = FileStore(tmp_path / "trust.json")
        state = _make_state()
        store.put(state.pair_id, state)
        store.delete(state.pair_id)
        assert store.get(state.pair_id) is None

    def test_delete_nonexistent_noop(self, tmp_path: pytest.TempPathFactory) -> None:
        store = FileStore(tmp_path / "trust.json")
        store.delete("nonexistent")  # Should not raise

    def test_all_pairs_missing_file(self, tmp_path: pytest.TempPathFactory) -> None:
        store = FileStore(tmp_path / "trust.json")
        assert store.all_pairs() == []

    def test_existing_empty_file_loads_as_empty(
        self, tmp_path: pytest.TempPathFactory
    ) -> None:
        """An existing but empty file is loaded as an empty store, not a crash."""
        path = tmp_path / "trust.json"
        path.write_text("")
        store = FileStore(path)
        assert store.all_pairs() == []
        assert store.get("anything") is None

    def test_existing_whitespace_only_file_loads_as_empty(
        self, tmp_path: pytest.TempPathFactory
    ) -> None:
        """A file containing only whitespace hits the empty-content load branch."""
        path = tmp_path / "trust.json"
        path.write_text("   \n\t  \n")
        store = FileStore(path)
        assert store.all_pairs() == []

    def test_all_pairs_with_data(self, tmp_path: pytest.TempPathFactory) -> None:
        store = FileStore(tmp_path / "trust.json")
        store.put("pair-1", _make_state("pair-1"))
        store.put("pair-2", _make_state("pair-2"))
        assert set(store.all_pairs()) == {"pair-1", "pair-2"}

    def test_file_created_on_put(self, tmp_path: pytest.TempPathFactory) -> None:
        path = tmp_path / "subdir" / "trust.json"
        path.parent.mkdir()
        store = FileStore(path)
        store.put("abc", _make_state())
        assert path.exists()

    def test_satisfies_protocol(self, tmp_path: pytest.TempPathFactory) -> None:
        store = FileStore(tmp_path / "trust.json")
        assert isinstance(store, TrustStore)
