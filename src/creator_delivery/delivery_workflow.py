from __future__ import annotations

from collections.abc import Callable
from typing import Literal, Protocol

try:
    from pydantic import BaseModel, Field
except ModuleNotFoundError:  # Keep the core workflow usable in the test-only runtime.
    class _Field:
        def __init__(self, *, min_length: int | None = None, max_length: int | None = None,
                     pattern: str | None = None) -> None:
            self.min_length = min_length
            self.max_length = max_length
            self.pattern = pattern

    def Field(*, min_length: int | None = None, max_length: int | None = None,
              pattern: str | None = None) -> _Field:
        return _Field(min_length=min_length, max_length=max_length, pattern=pattern)

    class BaseModel:
        def __init__(self, **values: object) -> None:
            annotations = getattr(type(self), "__annotations__", {})
            missing = [name for name in annotations if name not in values]
            if missing:
                raise ValueError(f"missing fields: {', '.join(missing)}")
            for name, value in values.items():
                constraint = getattr(type(self), name, None)
                if isinstance(constraint, _Field) and isinstance(value, str):
                    if constraint.min_length is not None and len(value) < constraint.min_length:
                        raise ValueError(f"{name} is too short")
                    if constraint.max_length is not None and len(value) > constraint.max_length:
                        raise ValueError(f"{name} is too long")
                    if constraint.pattern is not None:
                        import re
                        if re.search(constraint.pattern, value) is None:
                            raise ValueError(f"{name} has an invalid format")
                if name == "processing_state" and value not in {
                    "queued", "processing", "completed", "failed"
                }:
                    raise ValueError("processing_state has an invalid value")
                setattr(self, name, value)

        def model_dump(self) -> dict[str, object]:
            return {name: getattr(self, name) for name in self.__annotations__}


class RealtimeGateway(Protocol):
    create_channel: Callable[[str, str], dict[str, object]]
    issue_token: Callable[[str, str], dict[str, object]]
    publish_ready: Callable[
        [str, str, dict[str, object], str], dict[str, object]
    ]


class AssetDeliveryRequest(BaseModel):
    request_id: str = Field(min_length=8, max_length=128)
    asset_id: str = Field(min_length=1, max_length=128)
    creator_id: str = Field(min_length=1, max_length=128)
    processing_job_id: str = Field(min_length=1, max_length=128)
    processing_state: Literal["queued", "processing", "completed", "failed"]
    playback_url: str = Field(pattern=r"^https://")


class DeliveryBlocked(Exception):
    pass


class DeliveryReceipt(BaseModel):
    asset_id: str
    channel: str
    state: Literal["delivered"]
    client_token: str


def deliver_asset(
    request: AssetDeliveryRequest, realtime: RealtimeGateway
) -> DeliveryReceipt:
    if request.processing_state != "completed":
        raise DeliveryBlocked("asset processing must be completed before creator delivery")

    channel = f"asset:{request.asset_id}"
    realtime.create_channel(channel, request.request_id)
    token_data = realtime.issue_token(request.creator_id, channel)
    realtime.publish_ready(
        channel,
        request.creator_id,
        {
            "asset_id": request.asset_id,
            "processing_job_id": request.processing_job_id,
            "playback_url": request.playback_url,
        },
        request.request_id,
    )
    return DeliveryReceipt(
        asset_id=request.asset_id,
        channel=channel,
        state="delivered",
        client_token=str(token_data["token"]),
    )
