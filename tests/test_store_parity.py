"""Parity tests: every TrustStore implementation must behave identically.

Run a single test matrix against MemoryStore and FulcrumStore to prove
they are interchangeable on the TrustStore protocol.
"""

from __future__ import annotations

import pytest

from fulcrum_trust.stores.base import TrustStore
from fulcrum_trust.stores.fulcrum import FulcrumStore
from fulcrum_trust.stores.memory import MemoryStore
from fulcrum_trust.types import TrustState


class _NoopResponse:
    def __enter__(self) -> _NoopResponse:
        return self

    def __exit__(self, *_: object) -> None:
        pass


def _make_state(pair_id: str = "agent-a|agent-b") -> TrustState:
    return TrustState(
        pair_id=pair_id,
        agent_a="agent-a",
        agent_b="agent-b",
        alpha=3.0,
        beta_val=2.0,
        interaction_count=5,
    )


def _memory_factory() -> MemoryStore:
    return MemoryStore()


def _fulcrum_factory(monkeypatch: pytest.MonkeyPatch) -> FulcrumStore:
    """FulcrumStore with HTTP POST stubbed to no-op (parity = local behavior only)."""
    monkeypatch.setattr(
        "fulcrum_trust.stores.fulcrum.urllib.request.urlopen",
        lambda *_a, **_kw: _NoopResponse(),
    )
    return FulcrumStore(api_key="parity-test-key", base_url="http://localhost:9999")


@pytest.fixture(params=["memory", "fulcrum"], ids=["MemoryStore", "FulcrumStore"])
def store(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> TrustStore:
    if request.param == "memory":
        return _memory_factory()
    return _fulcrum_factory(monkeypatch)


class TestStoreProtocolParity:
    """Every test runs against both MemoryStore and FulcrumStore."""

    def test_satisfies_protocol(self, store: TrustStore) -> None:
        assert isinstance(store, TrustStore)

    def test_get_unknown_returns_none(self, store: TrustStore) -> None:
        assert store.get("nonexistent") is None

    def test_put_then_get(self, store: TrustStore) -> None:
        state = _make_state()
        store.put(state.pair_id, state)
        result = store.get(state.pair_id)
        assert result is not None
        assert result.pair_id == state.pair_id
        assert result.alpha == pytest.approx(state.alpha)
        assert result.beta_val == pytest.approx(state.beta_val)
        assert result.trust_score == pytest.approx(state.trust_score)

    def test_overwrite_on_put(self, store: TrustStore) -> None:
        state1 = _make_state()
        state1.alpha = 2.0
        store.put(state1.pair_id, state1)

        state2 = _make_state()
        state2.alpha = 8.0
        store.put(state2.pair_id, state2)

        result = store.get(state2.pair_id)
        assert result is not None
        assert result.alpha == pytest.approx(8.0)

    def test_delete_existing(self, store: TrustStore) -> None:
        state = _make_state()
        store.put(state.pair_id, state)
        store.delete(state.pair_id)
        assert store.get(state.pair_id) is None

    def test_delete_nonexistent_noop(self, store: TrustStore) -> None:
        store.delete("nonexistent")  # must not raise

    def test_all_pairs_empty(self, store: TrustStore) -> None:
        assert store.all_pairs() == []

    def test_all_pairs_with_data(self, store: TrustStore) -> None:
        store.put("pair-1", _make_state("pair-1"))
        store.put("pair-2", _make_state("pair-2"))
        assert set(store.all_pairs()) == {"pair-1", "pair-2"}

    def test_multiple_pairs_independent(self, store: TrustStore) -> None:
        state_a = _make_state("pair-a")
        state_b = _make_state("pair-b")
        store.put("pair-a", state_a)
        store.put("pair-b", state_b)
        store.delete("pair-a")
        assert store.get("pair-a") is None
        assert store.get("pair-b") is not None
