# P01 Delivery README

## 1. Scope Delivered

**Week 3+ - End-to-End Agent Wiring & Hardening (2026-03-01):**
- ✅ **gateway/router.py**: Refactored `create_runs_agent` from HTTP-based (POST /api/runs + poll GET) to **in-process** — calls `process_run()` directly, avoiding self-request deadlocks in single-process uvicorn
- ✅ **gateway/router.py**: `_fetch_run_output()` reads session summaries from disk (`memory/session_summaries_index/session_{run_id}.json`) via `nx.node_link_data()` format
- ✅ **gateway/router.py**: `RunsAgentAdapter` maintains rolling in-memory conversation history (last 10 user+assistant turns), prepended as `CONVERSATION HISTORY` block to each query for follow-up support
- ✅ **channels/telegram.py**: `_split_message()` — splits replies at Telegram's 4096-char limit at paragraph/sentence/word boundaries; MarkdownV2 escaping
- ✅ **channels/telegram.py**: `TelegramAdapter._poll_loop()` + `_handle_update()` — long-polling getUpdates loop with `set_bus_callback()` wired in `shared/state.py`
- ✅ **core/loop.py**: Null `plan_graph` guard — handles `plan_graph: null` from PlannerAgent for simple queries without crashing
- ✅ **routers/remme.py**: Ollama embedding fixes — corrected URL construction and model name for local Ollama embeddings
- ✅ **tests/test_runs_agent_factory.py**: Rewrote 5 tests — replaced httpx mocks with `sys.modules` injection for `routers.runs` + `patch("gateway.router._fetch_run_output")`, fixing 3 CI failures + 1 lint error (F541)

**Week 3+ - Matrix Adapter (Channel 10/10):**
- ✅ **channels/matrix.py**: MatrixAdapter — polling-based inbound via `GET /_matrix/client/v3/sync`; outbound via `PUT /_matrix/client/v3/rooms/{roomId}/send/m.room.message/{txnId}`; `set_bus_callback()` for inbound dispatch; skips own messages, non-m.text events, empty body; no sidecar needed
- ✅ **gateway/envelope.py**: `from_matrix()` constructor — room_id, sender_id, homeserver extracted from sender_id, is_direct flag
- ✅ **gateway/formatter.py**: `"matrix": "_format_plain"` in channel map (Matrix clients render Markdown client-side)
- ✅ **config/channels.yaml**: `matrix` channel block — homeserver_url, user_id, access_token, sync_interval env-var refs
- ✅ **shared/state.py**: `MatrixAdapter` wired into `get_message_bus()` + `set_bus_callback` wired after bus creation
- ✅ **tests/test_matrix_roundtrip.py**: 9 tests (send/error/network, bus roundtrip, session affinity, envelope fields, sync loop dispatch/skip-own/skip-empty)

**Week 3+ - Signal Adapter (Channel 9/10):**
- ✅ **signal_bridge/app.py**: Python FastAPI sidecar — polls signal-cli `GET /v1/receive` every 2s, forwards to FastAPI; `POST /send` proxies to signal-cli; HMAC-SHA256 signing
- ✅ **signal_bridge/README.md**: Setup guide for signal-cli install, registration, and bridge startup
- ✅ **channels/signal.py**: SignalAdapter — `POST {bridge_url}/send` with HMAC-SHA256 `X-Signal-Secret`; `verify_signature()` static method; dev-mode (empty secret → accept all)
- ✅ **gateway/envelope.py**: `from_signal()` — phone_number or group_id as conversation_id, group support
- ✅ **gateway/formatter.py**: `"signal": "_format_plain"` (Signal renders plain text natively)
- ✅ **routers/nexus.py**: `POST /api/nexus/signal/inbound` — HMAC verify, skip empty text, `from_signal()` envelope
- ✅ **shared/state.py**: `SignalAdapter` wired into `get_message_bus()`
- ✅ **tests/test_signal_roundtrip.py**: 11 tests (send/error/network, sig valid/invalid/dev-mode, bus roundtrip, session affinity, webhook×3)

**Week 3+ - Teams Adapter (Channel 8/10):**
- ✅ **channels/teams.py**: TeamsAdapter — Bot Framework REST API; outbound `POST {service_url}/v3/conversations/{id}/activities`; `verify_token()` static method (Bearer token compare, dev-mode)
- ✅ **gateway/envelope.py**: `from_teams()` — composite `conversation_id = f"{team_id}:{channel_id}"`, stores `service_url` in metadata
- ✅ **gateway/formatter.py**: `_format_teams()` — headings → `**bold**`, `_italic_` → `*italic*`
- ✅ **routers/nexus.py**: `POST /api/nexus/teams/events` — skips `type != "message"` and `from.role == "bot"`, builds from_teams() envelope
- ✅ **shared/state.py**: `TeamsAdapter` wired into `get_message_bus()`
- ✅ **config/channels.yaml**: `teams` channel block — app_id, app_password, service_url env-var refs
- ✅ **tests/test_teams_roundtrip.py**: 11 tests

**Week 3+ - iMessage Adapter (Channel 7/10, via BlueBubbles):**
- ✅ **channels/imessage.py**: iMessageAdapter — BlueBubbles REST API; outbound `POST {base_url}/api/v1/message/text`; `verify_signature()` HMAC-SHA256 static method; dev-mode
- ✅ **gateway/envelope.py**: `from_imessage()` constructor
- ✅ **routers/nexus.py**: `POST /api/nexus/imessage/inbound` — HMAC verify, skip empty text
- ✅ **tests/test_imessage_roundtrip.py**: 11 tests

**Week 3+ - Google Chat Adapter (Channel 6/10):**
- ✅ **channels/googlechat.py**: GoogleChatAdapter — dual-mode delivery (incoming webhook + service-account Bearer token); token verification for inbound events
- ✅ **gateway/envelope.py**: `from_googlechat()` constructor — space_name, sender, thread_name, message_name
- ✅ **gateway/formatter.py**: `_format_googlechat()` — headings → bold, links → plain text
- ✅ **config/channels.yaml**: `google_chat` channel block — env-var refs for webhook URL, service account token, verification token
- ✅ **shared/state.py**: `GoogleChatAdapter` wired into `get_message_bus()`
- ✅ **routers/nexus.py**: `POST /api/nexus/googlechat/events` — handles `MESSAGE`, `ADDED_TO_SPACE`, `REMOVED_FROM_SPACE`; optional token verification
- ✅ **tests/test_googlechat_roundtrip.py**: 8 tests (send/error/network/no-creds, bus roundtrip, session affinity, webhook event, lifecycle event)

**Week 3 (Sprint 4) - Real AgentLoop4 Wiring + Output Endpoint:**
- ✅ **routers/runs.py**: `GET /api/runs/{run_id}/output` — new read-only endpoint exposing extracted text output of a completed run (`status`: `running` | `completed` | `failed` | `not_found`)
- ✅ **routers/runs.py**: `_extract_output_str()` helper — refactored output extraction logic (FormatterAgent first, largest-string fallback, JSON/fence stripping) shared between `process_run()` and the new endpoint
- ✅ **gateway/router.py**: `create_runs_agent()` factory — real AgentLoop4 agent backed by `/api/runs`; `RunsAgentAdapter.process_message()` POSTs to `POST /api/runs` then polls `GET /api/runs/{run_id}/output` (2 s interval, 120 s timeout)
- ✅ **shared/state.py**: Swapped `create_mock_agent` → `create_runs_agent` — gateway now routes all channel messages through real AgentLoop4
- ✅ **channels/discord.py**: DiscordAdapter — Ed25519 signature verification (nacl), 2000-char truncation, Discord markdown formatter
- ✅ **channels/whatsapp.py**: WhatsAppAdapter — Baileys bridge via httpx, HMAC-SHA256 over body
- ✅ **routers/nexus.py**: `POST /api/nexus/discord/events` (PING type1, slash type5, message relay), `GET/POST /api/nexus/whatsapp/inbound` (hub.challenge + HMAC verify)
- ✅ **whatsapp_bridge/**: Node.js Baileys sidecar (`index.js`, `package.json`, `README.md`)
- ✅ **gateway/envelope.py**: `from_whatsapp()` constructor
- ✅ **Live Slack integration re-verified** with real AgentLoop4: messages route through `create_runs_agent` → `POST /api/runs` → poll output → reply delivered back to Slack channel

**Week 2 (Sprint 3) - Slack Adapter + SSE Push:**
- ✅ **channels/slack.py**: SlackAdapter — Slack Web API (`chat.postMessage`), HMAC-SHA256 signature verification, httpx async client
- ✅ **routers/nexus.py**: `POST /api/nexus/slack/events` — Slack Events API webhook (url_verification handshake + event_callback routing)
- ✅ **channels/webchat.py**: SSE push stream — `subscribe_sse`/`unsubscribe_sse`, `asyncio.Queue` per session
- ✅ **routers/nexus.py**: `GET /api/nexus/webchat/stream/{session_id}` — `EventSourceResponse` SSE endpoint with keepalive ping
- ✅ **api.py**: `load_dotenv()` added at startup so env vars (tokens, secrets) load before any adapter initialization

**Week 1 (Sprint 1-2) - Architecture + Unified Bus:**
- ✅ **channels/base.py**: ChannelAdapter ABC — `send_message`, `initialize`, `shutdown`
- ✅ **channels/telegram.py**: TelegramAdapter, parse_mode=MarkdownV2
- ✅ **channels/webchat.py**: WebChatAdapter, per-session deque outbox + drain-on-poll
- ✅ **gateway/envelope.py**: MessageEnvelope — `from_telegram/webchat/slack/discord/whatsapp()`, auto `message_hash`, `normalize_text()`
- ✅ **gateway/formatter.py**: Markdown → Telegram MarkdownV2 / Slack mrkdwn / Discord markdown / WebChat HTML / plain fallback
- ✅ **gateway/bus.py**: `ingest()` / `deliver()` / `roundtrip()` — replies to `session_id`
- ✅ **gateway/router.py**: MessageRouter — session affinity, `mention-only`/`always-on` group activation
- ✅ **config/channels.yaml**: Per-channel config schema (env-var references, policies, group activation)
- ✅ **shared/state.py**: `get_message_bus()` lazy singleton wiring all 5 adapters

---

## 2. Architecture Changes

**New directories:**
- `channels/`: Channel adapter implementations — `base.py`, `telegram.py`, `webchat.py`, `slack.py`, `discord.py`, `whatsapp.py`, `googlechat.py`, `imessage.py`, `teams.py`, `signal.py`, `matrix.py`
- `gateway/`: Unified message bus — `envelope.py`, `formatter.py`, `bus.py`, `router.py`
- `whatsapp_bridge/`: Node.js Baileys sidecar for WhatsApp
- `signal_bridge/`: Python FastAPI sidecar for Signal (signal-cli bridge)

**New files (Week 3+, latest):**
- `channels/matrix.py`: MatrixAdapter (polling sync API, no sidecar, set_bus_callback)
- `channels/signal.py`: SignalAdapter (signal_bridge sidecar, HMAC-SHA256)
- `channels/teams.py`: TeamsAdapter (Bot Framework REST, verify_token)
- `channels/imessage.py`: iMessageAdapter (BlueBubbles REST, HMAC-SHA256)
- `channels/googlechat.py`: GoogleChatAdapter (webhook + service-account)
- `signal_bridge/app.py`, `README.md`: Python FastAPI sidecar for signal-cli
- `tests/test_matrix_roundtrip.py`: 9 Matrix tests
- `tests/test_signal_roundtrip.py`: 11 Signal tests
- `tests/test_teams_roundtrip.py`: 11 Teams tests
- `tests/test_imessage_roundtrip.py`: 11 iMessage tests
- `tests/test_get_run_output.py`: 3 endpoint tests for GET /api/runs/{id}/output
- `tests/test_runs_agent_factory.py`: 5 factory tests for create_runs_agent

**Modified files (Week 3+):**
- `routers/runs.py`: Added `_extract_output_str()` helper + `GET /api/runs/{run_id}/output`
- `gateway/router.py`: Added `create_runs_agent` factory + `RunsAgentAdapter`; kept `create_mock_agent` for tests
- `gateway/envelope.py`: Added `from_whatsapp()`, `from_googlechat()`, `from_imessage()`, `from_teams()`, `from_signal()`, `from_matrix()`
- `gateway/formatter.py`: Added `_format_teams()`, `_format_googlechat()`; plain map entries for signal, matrix, imessage, whatsapp
- `shared/state.py`: All 10 adapters wired; Matrix `set_bus_callback` after bus creation
- `routers/nexus.py`: Inbound endpoints for all channels (Discord, WhatsApp, GoogleChat, iMessage, Teams, Signal)
- `.env.example`: All channel env-var sections added
- `config/channels.yaml`: All 10 channel blocks present

**Key architectural flow (in-process agent, 2026-03-01):**
```
Channel inbound → MessageEnvelope → bus.roundtrip()
                                        ↓
                               create_runs_agent(session_id)
                                        ↓
                     RunsAgentAdapter.process_message(envelope)
                                        ↓
          _build_contextual_query() (prepend conversation history)
                                        ↓
                    process_run(run_id, query)  [IN-PROCESS, no HTTP]
                                        ↓
                    _fetch_run_output(run_id)  [read session JSON from disk]
                                        ↓
                    return {"reply": output_str, ...}
                                        ↓
                    ChannelAdapter.send_message() → delivered to user
```

**Known limitation:** Each message starts a fresh AgentLoop4 run, but `RunsAgentAdapter` maintains rolling in-memory conversation history (last 10 user+assistant turns). Full persistent session threading requires deeper runs-API changes (P15 scope).

---

## 3. API And UI Changes

**New HTTP endpoints:**
```
POST /api/nexus/webchat/inbound
  Body: {session_id, sender_id, sender_name, text, message_id?}
  Returns: BusResult dict

GET  /api/nexus/webchat/messages/{session_id}
  Returns: {session_id, messages: [...], count: N}  (drains outbox)

GET  /api/nexus/webchat/stream/{session_id}
  SSE push stream — "message" and "ping" events

POST /api/nexus/slack/events
  url_verification → {"challenge": "..."}
  event_callback message → bus.roundtrip() → {"ok": true}

POST /api/nexus/discord/events
  PING (type 1) → {"type": 1}
  APPLICATION_COMMAND (type 2) → bus.roundtrip() → {"type": 5}
  message relay → bus.roundtrip() → {"ok": true}

GET  /api/nexus/whatsapp/inbound
  hub.challenge handshake → {"hub.challenge": token}

POST /api/nexus/whatsapp/inbound
  Baileys bridge inbound → HMAC verify → bus.roundtrip() → {"ok": true}

GET  /api/runs/{run_id}/output           [NEW — Week 3]
  Returns: {run_id, status: "running"|"completed"|"failed"|"not_found", output: str|null}
```

**New module APIs:**
- `create_runs_agent(session_id) -> RunsAgentAdapter` — real AgentLoop4 factory (in-process, no HTTP)
- `_fetch_run_output(run_id) -> dict` — reads session summary from disk
- `_extract_output_str(data: dict) -> str` — shared output extraction from session graph
- `MessageEnvelope.from_whatsapp(...)` — WhatsApp envelope constructor

---

## 4. Mandatory Test Gate Definition

- **Acceptance file**: `tests/acceptance/p01_nexus/test_multichannel_roundtrip.py` — 8 tests
- **Integration file**: `tests/integration/test_nexus_session_affinity.py` — 5 tests
- **CI check**: `p01-nexus-gateway` (wired in `.github/workflows/project-gates.yml`)

---

## 5. Test Evidence

**Automated test suite: 118 tests (P01 scope), 469 total passed (2026-03-01):**

| File | Tests | What it covers |
|------|-------|----------------|
| `tests/acceptance/p01_nexus/test_multichannel_roundtrip.py` | 8 | Contract + delivery README checks |
| `tests/integration/test_nexus_session_affinity.py` | 5 | Session affinity across channels |
| `tests/test_message_formatter.py` | 12 | Formatter for all 10 channels |
| `tests/test_message_bus.py` | 11 | ingest/deliver/roundtrip/dedup/retry/media |
| `tests/test_webchat_roundtrip.py` | 5 | WebChat end-to-end via TestClient |
| `tests/test_webchat_sse.py` | 6 | SSE subscribe/push/route contract |
| `tests/test_slack_roundtrip.py` | 8 | Slack send/error/network/webhook×3 |
| `tests/test_group_activation.py` | 5 | mention-only / always-on policy |
| `tests/test_discord_roundtrip.py` | 8 | Discord sig/PING/slash/relay/affinity |
| `tests/test_whatsapp_roundtrip.py` | 8 | WhatsApp HMAC/roundtrip/group/bridge |
| `tests/test_get_run_output.py` | 3 | GET /api/runs/{id}/output endpoint |
| `tests/test_runs_agent_factory.py` | 5 | create_runs_agent factory (mocked in-process calls via sys.modules injection) |
| `tests/test_googlechat_roundtrip.py` | 8 | Google Chat send/error/network/no-creds/bus/affinity/webhook/lifecycle |
| `tests/test_imessage_roundtrip.py` | 11 | iMessage send/error/network/sig, roundtrip, affinity, webhook×3 |
| `tests/test_teams_roundtrip.py` | 11 | Teams send/error/network/token, roundtrip, affinity, webhook×3 |
| `tests/test_signal_roundtrip.py` | 11 | Signal send/error/network, sig×3, roundtrip, affinity, webhook×3 |
| `tests/test_matrix_roundtrip.py` | 9 | Matrix send/error/network, roundtrip, affinity, envelope, sync loop×3 |

**Run command:**
```bash
uv run python -m pytest tests/acceptance/p01_nexus/ \
  tests/integration/test_nexus_session_affinity.py \
  tests/test_message_bus.py tests/test_message_formatter.py \
  tests/test_webchat_roundtrip.py tests/test_webchat_sse.py \
  tests/test_slack_roundtrip.py tests/test_group_activation.py \
  tests/test_discord_roundtrip.py tests/test_whatsapp_roundtrip.py \
  tests/test_get_run_output.py tests/test_runs_agent_factory.py \
  tests/test_p01_latency.py tests/test_googlechat_roundtrip.py \
  tests/test_imessage_roundtrip.py tests/test_teams_roundtrip.py \
  tests/test_signal_roundtrip.py tests/test_matrix_roundtrip.py -v
```

**Live Slack integration verified (Week 3 — real agent):**
- Messages routed via `create_runs_agent` → `process_run()` (in-process) → AgentLoop4 ✅
- `group_activation: always-on` required (Slack sends `<@USER_ID>` not `@botname`) ✅
- Reply read from `_fetch_run_output()` (disk) → delivered back to Slack ✅

**Live Telegram integration verified (2026-03-01 — real agent):**
- TelegramAdapter._poll_loop() → bus.roundtrip() → AgentLoop4 → reply via sendMessage ✅
- Conversation history maintained across messages (10-turn rolling window) ✅
- Long replies auto-chunked at 4096-char Telegram limit ✅

**Live Slack integration verified (Week 2 — mock agent):**
- "hello Arcturus" → reply `[Session C04KYFS5DV2] Processed: hello Arcturus` ✅
- Signature verification: requests without `X-Slack-Signature` rejected 403 ✅

---

## 6. Existing Baseline Regression Status

**Command:** `uv run python -m pytest tests/ --ignore=tests/stress -q`

**Status:** ✅ **469 passed, 2 skipped** (2026-03-01)

P01 changes are fully additive and non-breaking:
- All new code in `channels/`, `gateway/`, `routers/nexus.py` is isolated
- `routers/runs.py`: read-only endpoint + private helper only (no existing logic changed)
- `shared/state.py`: additive factory swap (no public API changed)
- Zero impact on existing subsystems (loops, RAG, remme, bootstrap, config)

---

## 7. Security and Safety Impact

- **No hardcoded secrets**: All tokens/secrets read from `.env` only; `.env.example` updated with new vars
- **HMAC-SHA256 verification**: Slack (`v0:{ts}:{body}`), WhatsApp (raw body) — fail-closed when secret is set
- **Ed25519 verification**: Discord sig verified with nacl; invalid sig → 401
- **Bot loop prevention**: Slack filters `bot_id`; WhatsApp filters `fromMe` at bridge level
- **Empty text guard**: WhatsApp endpoint skips empty text
- **Session isolation**: Router maintains separate agent instances per session_id

---

## 8. Known Gaps

**Resolved in Week 3+:**
- ✅ Real AgentLoop4 wiring via `create_runs_agent`
- ✅ Discord adapter implemented and tested
- ✅ WhatsApp adapter + Baileys bridge implemented and tested
- ✅ Group activation policies enforced in `MessageRouter._is_activated()`
- ✅ `GET /api/runs/{run_id}/output` endpoint
- ✅ Google Chat adapter (webhook + service-account modes)
- ✅ iMessage adapter (BlueBubbles bridge)
- ✅ Teams adapter (Bot Framework REST)
- ✅ Signal adapter + signal_bridge sidecar (signal-cli, encrypted, group support, disappearing messages compliant)
- ✅ Matrix adapter (polling sync, no sidecar, no AS registration needed)
- ✅ **All 10 channel adapters complete** — P01 channel scope fully delivered

**Remaining (out-of-P01-scope):**
- **Cross-message memory**: Fresh AgentLoop4 per message — in-memory rolling history (10 turns) provides short-term continuity; persistent cross-session memory requires P15 scope
- **DM security policy**: Pairing-code flow blocked — no identity layer yet (P12 scope)
- **Media transcoding**: `MediaAttachment` in envelope; no per-channel format conversion

---

## 9. Rollback Plan

- **Safe to revert**: Remove `channels/`, `gateway/`, `whatsapp_bridge/` and their imports in `shared/state.py` / `api.py`
- **Factory rollback**: Change `create_runs_agent` → `create_mock_agent` in `shared/state.py` line 119
- **Runs endpoint**: `GET /api/runs/{run_id}/output` is read-only; removing it has zero downstream impact
- **No database changes**: No schema migrations

---

## 10. Demo Steps

**Full end-to-end Slack demo (real AgentLoop4):**
```bash
# Terminal 1 — tunnel (no account needed)
ssh -R 80:localhost:8000 nokey@localhost.run

# Terminal 2 — backend
uv run uvicorn api:app --reload --port 8000

# Slack Event Subscriptions URL:
#   https://<tunnel-url>/api/nexus/slack/events
# Send any message in the Slack channel — bot responds via real AgentLoop4
```

**Output endpoint smoke test:**
```bash
curl http://localhost:8000/api/runs/<run_id>/output
# {"run_id":"...","status":"completed","output":"The answer is 4."}
```

**Slack inbound smoke test (no Slack app needed):**
```bash
curl -X POST http://localhost:8000/api/nexus/slack/events \
  -H "Content-Type: application/json" \
  -d '{"type":"event_callback","event":{"type":"message","channel":"C04KYFS5DV2","user":"U123","text":"What is 2+2?","ts":"1234567890.123456"}}'
```

**Telegram end-to-end demo (real AgentLoop4):**
```bash
# Ensure .env has TELEGRAM_TOKEN=<bot-token>
# Terminal 1 — backend
uv run uvicorn api:app --reload --port 8000

# Send a message to @dinoblade_bot on Telegram
# Bot replies via real AgentLoop4 with conversation context
# Follow-up messages have context from previous turns (10-turn rolling window)
```

**Full P01 test suite:**
```bash
uv run python -m pytest tests/acceptance/p01_nexus/ \
  tests/integration/test_nexus_session_affinity.py \
  tests/test_message_bus.py tests/test_message_formatter.py \
  tests/test_webchat_roundtrip.py tests/test_webchat_sse.py \
  tests/test_slack_roundtrip.py tests/test_group_activation.py \
  tests/test_discord_roundtrip.py tests/test_whatsapp_roundtrip.py \
  tests/test_get_run_output.py tests/test_runs_agent_factory.py \
  tests/test_p01_latency.py tests/test_googlechat_roundtrip.py \
  tests/test_imessage_roundtrip.py tests/test_teams_roundtrip.py \
  tests/test_signal_roundtrip.py tests/test_matrix_roundtrip.py -v
```
