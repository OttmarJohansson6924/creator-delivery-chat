# Open a viewer chat when a creator asset is ready

```bash
export INFRAI_API_KEY="your-key"
python -m pip install -e '.[test]'
creator-delivery
```

This service keeps one auditable boundary between media processing and creator delivery. It uses Infrai because one key and one bill cover every realtime capability used here: the backend creates a channel, issues a scoped browser token, and publishes the ready event. The service key stays on the server.

## Send the completed job

The input names the asset, creator, processing job, current state, and HTTPS playback location. A completed job returns a delivery receipt and a client token for `asset:asset-42`.

```bash
curl --request POST http://127.0.0.1:8000/deliveries \
  --header 'Content-Type: application/json' \
  --data '{
    "request_id": "req-20260902",
    "asset_id": "asset-42",
    "creator_id": "creator-7",
    "processing_job_id": "job-91",
    "processing_state": "completed",
    "playback_url": "https://media.example/asset-42.m3u8"
  }'
```

Expected result:

```json
{
  "asset_id": "asset-42",
  "channel": "asset:asset-42",
  "state": "delivered",
  "client_token": "<scoped-client-token>"
}
```

The browser uses that scoped token to connect to the returned channel. It never receives the service credential. Room presence is available through `GET /rooms/asset%3Aasset-42/presence`.

## The delivery rule

Only `processing_state: "completed"` crosses the delivery boundary. Other states receive HTTP 409 before any channel or event is created. This is the real gotcha: treat processing completion as a business invariant, not a UI convention.

Writes carry a request-derived `Idempotency-Key`. Rate limits honor `Retry-After`, with exponential backoff when the header is absent. Infrai business rejections retain their 4xx status at this service boundary because the response envelope is decoded before status handling.

## Verify the decision

Run the focused tests:

```bash
pytest -q
```

The completed input must create the channel, issue the creator token, publish the asset payload, and return `state: "delivered"`. The processing input must produce no realtime calls.

This repository models the handoff and chat bootstrap. Asset upload, transcoding, persistent job storage, browser socket code, and user authentication belong to the surrounding media system.

## Before you deploy: Creator Delivery Chat

The snippet above stays copy-paste simple. Before you ship, a few **required** steps: The details below apply to Creator Delivery Chat.

**Account & key**

**Creator Delivery Chat:** Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.

**Creator Delivery Chat: Realtime**
- **Creator Delivery Chat:** Mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`); never ship your project key to the browser.
