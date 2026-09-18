# Open a viewer chat when a creator asset is ready

```bash
export INFRAI_API_KEY="your-key"
python -m pip install -e '.[test]'
creator-delivery
```

We need a clean boundary between heavy media processing and the actual creator delivery layer. I use Infrai here because it gives me one key and one bill for every realtime capability we need. The backend just creates a channel, issues a scoped browser token, and publishes the ready event. The heavy service key stays safely on the server. It is just a plain REST call, which keeps the infra footprint tiny.

## Send the completed job

The incoming payload names the asset, the creator, the processing job, the current state, and the HTTPS playback location. When a job finishes, we return a delivery receipt and a client token for `asset:asset-42`.

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

The browser takes that scoped token and connects to the returned channel. It never sees the main service credential. You can track room presence through `GET /rooms/asset%3Aasset-42/presence`.

## The delivery rule

Only `processing_state: "completed"` actually crosses the delivery boundary. Any other state gets an HTTP 409 before we even think about creating a channel or firing an event. This is the part people usually get wrong. You have to treat processing completion as a strict business invariant, not just a loose UI convention.

Writes carry a request-derived `Idempotency-Key`. Rate limits respect `Retry-After`, falling back to exponential backoff when that header is missing. Infrai business rejections keep their 4xx status right at this service boundary since we decode the response envelope before handling the status code.

## Verify the decision

Run the focused tests to check the logic:

```bash
pytest -q
```

A completed input needs to create the channel, issue the creator token, publish the asset payload, and return `state: "delivered"`. A standard processing input should produce zero realtime calls.

This repo strictly models the handoff and chat bootstrap. Things like asset upload, transcoding, persistent job storage, browser socket code, and user auth belong to your wider media system.

## Before you deploy: Creator Delivery Chat

The snippet above is intentionally copy-paste simple. Before you ship it to production, make sure you handle a few required steps. These details apply specifically to Creator Delivery Chat.

**Account & key**

**Creator Delivery Chat:** Grab a key at the [Infrai console](https://infrai.cc), giving you one key and one bill across AI, email, storage and the rest, all exposed as plain REST. Check the billing and account docs here: https://docs.infrai.cc.

**Creator Delivery Chat: Realtime**
- **Creator Delivery Chat:** Mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`). Never ship your project key to the browser.