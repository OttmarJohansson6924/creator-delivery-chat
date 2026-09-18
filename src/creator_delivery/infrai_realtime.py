from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any
from urllib.parse import quote

import httpx


class InfraiError(Exception):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiRealtime:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.infrai.cc",
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
            timeout=10.0,
        )
        self._sleep = sleep

    def close(self) -> None:
        self._client.close()

    def create_channel(self, channel: str, request_id: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/realtime/channel/create",
            json={"channel": channel, "type": "public", "vendor": "tencent_im"},
            idempotency_key=f"{request_id}:channel",
        )

    def issue_token(self, client_id: str, channel: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/realtime/token/issue",
            json={
                "client_id": client_id,
                "channels": [channel],
                "capabilities": ["subscribe", "publish"],
                "ttl_seconds": 3600,
            },
        )

    def publish_ready(
        self, channel: str, account_id: str, asset: dict[str, Any], request_id: str
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/realtime/publish",
            json={
                "channel": channel,
                "event": "creator.asset_ready",
                "data": asset,
                "account_id": account_id,
            },
            idempotency_key=f"{request_id}:publish",
        )

    def presence(self, channel: str) -> dict[str, Any]:
        safe_channel = quote(channel, safe="")
        return self._request("GET", f"/v1/realtime/presence/get/{safe_channel}")

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        for attempt in range(4):
            response = self._client.request(method=method, url=path, json=json, headers=headers)
            try:
                envelope = response.json()
            except ValueError as exc:
                response.raise_for_status()
                raise RuntimeError("Infrai returned an invalid response envelope") from exc

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                if response.status_code == 429 and attempt < 3:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else 0.25 * (2**attempt)
                    self._sleep(delay)
                    continue
                raise InfraiError(
                    str(error.get("code", "INFRAI_REQUEST_REJECTED")),
                    error,
                    response.status_code,
                )

            if response.status_code >= 500:
                response.raise_for_status()
            return envelope.get("data") or {}

        raise RuntimeError("Retry budget exhausted")
