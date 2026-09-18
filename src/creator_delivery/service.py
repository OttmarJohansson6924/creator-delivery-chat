from __future__ import annotations

import os
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException

from .delivery_workflow import (
    AssetDeliveryRequest,
    DeliveryBlocked,
    DeliveryReceipt,
    deliver_asset,
)
from .infrai_realtime import InfraiError, InfraiRealtime

app = FastAPI(title="Creator delivery chat")


def realtime_client() -> InfraiRealtime:
    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise RuntimeError("INFRAI_API_KEY is required")
    client = InfraiRealtime(api_key)
    try:
        yield client
    finally:
        client.close()


@app.post("/deliveries", response_model=DeliveryReceipt, status_code=201)
def create_delivery(
    request: AssetDeliveryRequest,
    realtime: Annotated[InfraiRealtime, Depends(realtime_client)],
) -> DeliveryReceipt:
    try:
        return deliver_asset(request, realtime)
    except DeliveryBlocked as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InfraiError as exc:
        status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(
            status_code=status,
            detail={"code": exc.code, "message": exc.detail.get("message", exc.code)},
        ) from exc


@app.get("/rooms/{channel}/presence")
def get_presence(
    channel: str,
    realtime: Annotated[InfraiRealtime, Depends(realtime_client)],
) -> dict[str, object]:
    try:
        return realtime.presence(channel)
    except InfraiError as exc:
        status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=status, detail={"code": exc.code}) from exc


def run() -> None:
    import uvicorn

    uvicorn.run("creator_delivery.service:app", host="127.0.0.1", port=8000)
