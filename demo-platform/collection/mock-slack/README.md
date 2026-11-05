# Local incident workspace

Run the workspace from the repository root with `make -C demo-platform/collection mock-up`, then open `http://127.0.0.1:3100`. Docker Compose builds the dependency-free Node server and keeps thread state in the `bankir-1105-collection` volume. Node 22 or later can also run the app with `npm --prefix demo-platform/collection/mock-slack start`.

Operators choose a named colleague from the sender menu in the local collaboration fixture. A root message containing `@devin` starts one Fusion session; replies from every colleague reach the same session with the display name prepended. Earlier messages in a passive thread become context when a colleague first mentions Devin. The server polls the v3 messages endpoint and deduplicates Devin replies by event ID. Real Slack authentication and the native Slack integration remain separate products.

## Configuration

Set environment variables in the launching shell or inject secrets from the secret store. Never put keys in client code, committed files or command arguments.

| Variable | Purpose |
|---|---|
| `MOCK_SLACK_DEVIN_API_KEY` | Persona PAT, or a service-user key with session use and permission to read its sessions |
| `DEVIN_ORG_ID` | Target organization ID |
| `DEVIN_API_BASE` | API origin, normally `https://api.devin.ai`; dedicated deployments use their host plus `/api` |
| `DEVIN_WEB_BASE` | Webapp origin used for session links |
| `DEVIN_CREATE_AS_USER_ID` | Persona user ID when using a service key with `ImpersonateOrgSessions`; omit with a persona PAT |
| `DEVIN_MAX_ACU` | Session ACU limit, default 5, range 1 to 100 |
| `DEVIN_TRIGGER_ROUTE` | `session` by default; `webhook` sends matching roots to an automation instead |
| `DEVIN_WEBHOOK_ACTION` | `start_session` by default; `message_session` sends every turn to a dedicated long-running automation |
| `DEVIN_AUTOMATION_URL` | Incoming automation webhook URL; required in webhook mode |
| `DEVIN_WEBHOOK_SECRET` | Automation `X-Webhook-Secret`, required in webhook mode |
| `ALERTMANAGER_RECEIVER_SECRET` | Independent shared secret required by the raw Alertmanager receiver |
| `MOCK_SLACK_PORT` | Published loopback port, default 3100 |
| `STATE_FILE` | Native Node state location; Compose fixes the location at `/data/state.json` |
| `DEVIN_TRANSCRIPT_FILE` | Optional local read-mirror JSON path for a webhook session without a read API credential |

The create payload sets `devin_mode: fusion`, the ACU cap and the `bankir-1105` tag. The v3 create schema has no folder field. Move the proof session into the required folder from the persona's sidebar after creation, then verify ownership and mode through the read API. A read-only key cannot start sessions. A generic service key without impersonation creates service-owned sessions; use a persona PAT or explicit persona impersonation for persona attribution.

In automation mode the server posts `{message, channel, thread_id}` to the configured incoming webhook. With the default `start_session` action, a returned `session_id` or `devin_id` lets subsequent replies and polling use the session API credential. If the automation accepts the webhook without an ID, the thread shows the delivery receipt and retains subsequent context locally without firing another automation. Open the resulting session from the automation's history.

## Multi-turn webhook delivery

For repeated incident updates, set `DEVIN_TRIGGER_ROUTE=webhook` and `DEVIN_WEBHOOK_ACTION=message_session` in the launching shell, then choose incoming webhook, **Message existing session**, and **Create new session** as the destination in the persona's automation UI. The destination setting creates one long-running session for the automation. Set run as creator, Fusion, an ACU cap and an invocation limit that covers the expected updates. Configure the automation prompt to forward the incoming `message` body, preserving each author's display name.

The first matching thread claims the dedicated automation, and the server persists the binding before sending. Every later turn uses the same webhook, including after a destination session ID becomes known. Another thread is blocked visibly, and changing the automation URL cannot retarget an existing bound thread. Run one dedicated automation and persistent workspace state per incident thread; deleting state permits a new local binding to the same remote destination, so reuse the original state or create a fresh automation. Keep one server process per state file. A global automation destination cannot isolate several threads through the `thread_id` payload alone.

This path requires a webhook secret for writes. An optional read-scoped session credential supports API reply polling when the session ID is returned; an authenticated-browser read mirror supports replies when the webhook omits the ID. Set up the mirror from the automation's destination session. The mirror reads responses while subsequent workspace messages continue through the webhook, and the UI identifies both paths. A PAT remains an optional upgrade.

An operator who can read the resulting session in an authenticated browser can supply a local read mirror through `DEVIN_TRANSCRIPT_FILE`. The file has shape `{"items":[{"thread_id":"workspace-thread-id","session_id":"devin-32-hex-id","messages":[{"event_id":"source-event-id","source":"devin","message":"Read from the actual session","created_at":1793849000}]}]}`. Write updates atomically. The server matches an existing webhook thread, deduplicates event IDs and displays the source session link. The thread status identifies the read mirror. With `start_session`, follow-up messages stay local; with `message_session`, follow-up messages reach the dedicated automation. Operators supply authenticated browser-read updates separately. With Compose, put the file in the workspace volume and set the path under `/data`.

## Alertmanager input

The authenticated receiver accepts the standard raw Alertmanager body at `/receivers/alertmanager`, creates an Alertmanager bot thread in `#alerts` for each firing fingerprint and start time, and ignores repeated deliveries and resolved alerts. Set the receiver secret in the app's environment and the incident overlay's environment to the same value. Layer the receiver overlay after the existing incident files when starting the incident stack:

```sh
docker compose -p bankir-1105-incident \
  -f docker-compose.yml -f docker-compose.infra.yml \
  -f docker-compose.incident.yml \
  -f demo-platform/collection/incident.receiver.yml \
  up -d document-service postgres redis prometheus grafana jaeger alertmanager alert-sink
```

Start the workspace first: the overlay attaches Alertmanager to the workspace's private Compose network and addresses `mock-slack:3100` directly. The host listener stays on loopback. The local alert sink and the Slack sink remain unchanged. Do not point `SLACK_WEBHOOK_URL` at the raw receiver: Slack-formatted messages are a different payload.

## Alert storm forwarding

Set `ALERT_BATCH_WEBHOOK_URL` to a Devin incoming automation URL to collect new
firing alerts into a single webhook after a quiet window. Set
`ALERT_BATCH_WEBHOOK_SECRET` for the outgoing `X-Webhook-Secret` header.
`ALERT_BATCH_QUIET_MS` defaults to 90000; choose a longer window when scenarios
take different amounts of time to fire. Start mock Slack with these variables
before starting the incident stack with the receiver overlay, then run
`make arm SCENARIO=all` (or a comma list) with the same Compose project and files.

Each alert still gets a root post in `#alerts`. Batch mode sends raw alerts
only through the batch webhook, independently of the per-thread automation
binding. The JSON body contains `message`, `channel` and `alerts`; the message
lists alert names, scenarios, severities, summaries, start times and labels.
A bot note records delivery and a session link when the automation returns an
ID. Failed or interrupted delivery stays uncertain and requires an operator
check in automation history; the server does not retry a possibly accepted
batch. Pending alerts survive restarts in the workspace state file.

The Alertmanager route groups by `alertname` and `scenario`, with a 10-second
group wait. Raw receivers send every alert in each group (`max_alerts: 0`),
including multiple instances; Slack-formatted delivery and local gate captures
keep their existing routes.

## Recovery and cleanup

The server serializes concurrent replies and persists request IDs, so duplicate client submissions keep the original thread. Mappings survive process restarts. A remote timeout leaves an uncertain delivery visible; the server requires an operator check before any replacement work. Check the upstream history before starting a replacement thread.

Keep the published listener on loopback; there is no login or authorization between named colleagues. The JSON API rejects cross-origin browser writes. The Alertmanager endpoint requires its separate shared secret. API and webhook credentials remain inside the server process and never appear in state responses.

Run `make -C demo-platform/collection check test` for syntax checks and API-fixture integration tests. Stop with `make -C demo-platform/collection mock-down`. Add `-v` to the underlying Compose down command only when discarding recorded threads is intended. Revoke temporary keys and delete their stored secrets when the collection no longer needs live triggering.
