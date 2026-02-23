from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest

from fulcrum_trust import FulcrumStore, TrustManager, TrustOutcome


class _CaptureHandler(BaseHTTPRequestHandler):
    received: list[dict[str, Any]] = []

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return None

    def do_POST(self) -> None:  # noqa: N802
        body_len = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(body_len)
        payload = json.loads(raw_body.decode("utf-8"))

        self.__class__.received.append(
            {
                "path": self.path,
                "x_api_key": self.headers.get("X-API-Key"),
                "payload": payload,
            }
        )

        self.send_response(201)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')


def _start_capture_server() -> tuple[ThreadingHTTPServer, threading.Thread]:
    _CaptureHandler.received = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _CaptureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def test_trust_manager_put_emits_live_route_contract_payload() -> None:
    server, thread = _start_capture_server()
    tenant_id = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
    try:
        base_url = f"http://127.0.0.1:{server.server_port}"
        store = FulcrumStore(
            api_key="integration-key",
            base_url=base_url,
            timeout_seconds=1.0,
            tenant_id=tenant_id,
        )
        manager = TrustManager(store=store)

        state = manager.evaluate("live-agent-b", "live-agent-a", TrustOutcome.FAILURE)

        deadline = time.time() + 2.0
        while time.time() < deadline and len(_CaptureHandler.received) == 0:
            time.sleep(0.01)

        assert len(_CaptureHandler.received) == 1
        event = _CaptureHandler.received[0]
        assert event["path"] == "/api/trust/events"
        assert event["x_api_key"] == "integration-key"

        payload = event["payload"]
        assert payload["tenant_id"] == tenant_id
        assert payload["event_type"] == "TRUST_STATE_UPDATED"
        assert payload["pair_id"] == state.pair_id
        assert payload["trust_score"] == pytest.approx(state.trust_score)
        assert payload["payload"]["state"]["pair_id"] == state.pair_id
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2.0)
