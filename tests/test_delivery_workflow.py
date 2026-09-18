from creator_delivery.delivery_workflow import (
    AssetDeliveryRequest,
    DeliveryBlocked,
    deliver_asset,
)


class RecordingRealtime:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def create_channel(self, channel: str, request_id: str) -> dict[str, object]:
        self.calls.append(("create_channel", channel, request_id))
        return {"channel": channel}

    def issue_token(self, client_id: str, channel: str) -> dict[str, object]:
        self.calls.append(("issue_token", client_id, channel))
        return {"token": "browser-session-token"}

    def publish_ready(
        self, channel: str, account_id: str, asset: dict[str, object], request_id: str
    ) -> dict[str, object]:
        self.calls.append(("publish_ready", channel, account_id, asset, request_id))
        return {"published": True}


def request_with(state: str) -> AssetDeliveryRequest:
    return AssetDeliveryRequest(
        request_id="req-20260902",
        asset_id="asset-42",
        creator_id="creator-7",
        processing_job_id="job-91",
        processing_state=state,
        playback_url="https://media.example/asset-42.m3u8",
    )


def test_completed_asset_opens_room_and_publishes_delivery() -> None:
    realtime = RecordingRealtime()

    receipt = deliver_asset(request_with("completed"), realtime)  # type: ignore[arg-type]

    assert receipt.model_dump() == {
        "asset_id": "asset-42",
        "channel": "asset:asset-42",
        "state": "delivered",
        "client_token": "browser-session-token",
    }
    assert [call[0] for call in realtime.calls] == [
        "create_channel",
        "issue_token",
        "publish_ready",
    ]
    published_asset = realtime.calls[2][3]
    assert published_asset == {
        "asset_id": "asset-42",
        "processing_job_id": "job-91",
        "playback_url": "https://media.example/asset-42.m3u8",
    }


def test_processing_asset_cannot_be_delivered() -> None:
    realtime = RecordingRealtime()

    try:
        deliver_asset(request_with("processing"), realtime)  # type: ignore[arg-type]
    except DeliveryBlocked as exc:
        assert str(exc) == "asset processing must be completed before creator delivery"
    else:
        raise AssertionError("delivery should be blocked")

    assert realtime.calls == []
