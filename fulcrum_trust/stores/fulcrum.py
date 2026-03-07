from __future__ import annotations

import json
import logging
import socket
import urllib.error
import urllib.request
from dataclasses import asdict
from typing import Any
from urllib.parse import urljoin

from fulcrum_trust.stores.memory import MemoryStore
from fulcrum_trust.types import TrustState


class FulcrumStore:
    """Write-through store that mirrors trust state locally and ships events to Fulcrum.

    Local reads always come from in-process memory. Writes persist locally first, then
    best-effort POST to `/api/trust/events` with `X-API-Key` auth.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.fulcrumlayer.io",
        timeout_seconds: float = 2.0,
        tenant_id: str | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/") + "/"
        self._timeout_seconds = timeout_seconds
        self._tenant_id = tenant_id
        self._local = MemoryStore()
        self._logger = logging.getLogger("fulcrum_trust.fulcrum_store")

    def get(self, pair_id: str) -> TrustState | None:
        return self._local.get(pair_id)

    def put(self, pair_id: str, state: TrustState) -> None:
        # Write-through contract: update local memory first so caller continuity is guaranteed.
        self._local.put(pair_id, state)
        self._post_event(pair_id, state)

    def delete(self, pair_id: str) -> None:
        self._local.delete(pair_id)

    def all_pairs(self) -> list[str]:
        return self._local.all_pairs()

    def _post_event(self, pair_id: str, state: TrustState) -> None:
        payload: dict[str, Any] = {
            "tenant_id": self._tenant_id,
            "pair_id": pair_id,
            "event_type": "TRUST_STATE_UPDATED",
            "trust_score": state.trust_score,
            "payload": {
                "state": asdict(state),
            },
        }
        if payload["tenant_id"] is None:
            payload.pop("tenant_id")

        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            urljoin(self._base_url, "api/trust/events"),
            data=data,
            headers={
                "Content-Type": "application/json",
                "X-API-Key": self._api_key,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds):
                return
        except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as exc:
            self._logger.warning(
                "FulcrumStore fallback: trust event not shipped (%s)", exc
            )
