from __future__ import annotations

import json
import socket
import urllib.error
from typing import Any

import pytest

from fulcrum_trust.stores.base import TrustStore
from fulcrum_trust.stores.fulcrum import FulcrumStore
from fulcrum_trust.types import TrustState


def _make_state(pair_id: str = "agent-a:agent-b") -> TrustState:
    return TrustState(
        pair_id=pair_id,
        agent_a="agent-a",
        agent_b="agent-b",
        alpha=3.0,
        beta_val=2.0,
        interaction_count=5,
    )


class _DummyResponse:
    def __enter__(self) -> _DummyResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def test_satisfies_trust_store_protocol() -> None:
    store = FulcrumStore(api_key="test-key")
    assert isinstance(store, TrustStore)


def test_put_writes_local_state_even_when_remote_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise_urlerror(*_args: Any, **_kwargs: Any) -> _DummyResponse:
        raise urllib.error.URLError("backend unavailable")

    monkeypatch.setattr(
        "fulcrum_trust.stores.fulcrum.urllib.request.urlopen", _raise_urlerror
    )

    store = FulcrumStore(api_key="test-key", base_url="http://localhost:3000")
    state = _make_state()

    # Must not raise; fallback keeps local continuity.
    store.put(state.pair_id, state)

    persisted = store.get(state.pair_id)
    assert persisted is not None
    assert persisted.pair_id == state.pair_id
    assert persisted.trust_score == pytest.approx(state.trust_score)


def test_put_posts_expected_endpoint_headers_and_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def _capture(request: Any, timeout: float) -> _DummyResponse:
        captured["request"] = request
        captured["timeout"] = timeout
        return _DummyResponse()

    monkeypatch.setattr("fulcrum_trust.stores.fulcrum.urllib.request.urlopen", _capture)

    store = FulcrumStore(
        api_key="test-key",
        base_url="http://localhost:3000",
        timeout_seconds=1.5,
        tenant_id="a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
    )
    state = _make_state()
    store.put(state.pair_id, state)

    req = captured["request"]
    assert captured["timeout"] == pytest.approx(1.5)
    assert req.full_url == "http://localhost:3000/api/trust/events"
    assert req.get_method() == "POST"
    assert req.get_header("X-api-key") == "test-key"

    payload = json.loads(req.data.decode("utf-8"))
    assert payload["pair_id"] == state.pair_id
    assert payload["event_type"] == "TRUST_STATE_UPDATED"
    assert payload["trust_score"] == pytest.approx(state.trust_score)
    assert payload["tenant_id"] == "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"


@pytest.mark.parametrize(
    "exc",
    [
        urllib.error.URLError("network down"),
        TimeoutError("timed out"),
        socket.timeout("socket timeout"),
        OSError("connection reset"),
    ],
)
def test_put_never_raises_on_connectivity_failures(
    monkeypatch: pytest.MonkeyPatch,
    exc: BaseException,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def _raise(*_args: Any, **_kwargs: Any) -> _DummyResponse:
        raise exc

    monkeypatch.setattr("fulcrum_trust.stores.fulcrum.urllib.request.urlopen", _raise)

    store = FulcrumStore(api_key="test-key", base_url="http://localhost:3000")
    state = _make_state()

    with caplog.at_level("WARNING"):
        store.put(state.pair_id, state)

    assert "fallback: trust event not shipped" in caplog.text
    assert store.get(state.pair_id) is not None
