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
| `DEVIN_AUTOMATION_URL` | Incoming automation webhook URL; required in webhook mode |
| `DEVIN_WEBHOOK_SECRET` | Automation `X-Webhook-Secret`, required in webhook mode |
| `ALERTMANAGER_RECEIVER_SECRET` | Independent shared secret required by the raw Alertmanager receiver |
| `MOCK_SLACK_PORT` | Published loopback port, default 3100 |
| `STATE_FILE` | Native Node state location; Compose fixes the location at `/data/state.json` |
| `DEVIN_TRANSCRIPT_FILE` | Optional local read-mirror JSON path for a webhook session without a read API credential |

The create payload sets `devin_mode: fusion`, the ACU cap and the `bankir-1105` tag. The v3 create schema has no folder field. Move the proof session into the required folder from the persona's sidebar after creation, then verify ownership and mode through the read API. A read-only key cannot start sessions. A generic service key without impersonation creates service-owned sessions; use a persona PAT or explicit persona impersonation for persona attribution.

In automation mode the server posts `{message, channel, thread_id}` to the configured incoming webhook. If the automation returns `session_id` or `devin_id`, replies and polling use that session when a session API credential is configured. If the automation accepts the webhook without an ID, the thread shows the delivery receipt and retains subsequent context locally without firing another automation. Open the resulting session from the automation's history.

An operator who can read the resulting session in an authenticated browser can supply a local read mirror through `DEVIN_TRANSCRIPT_FILE`. The file has shape `{"items":[{"thread_id":"workspace-thread-id","session_id":"devin-32-hex-id","messages":[{"event_id":"source-event-id","source":"devin","message":"Read from the actual session","created_at":1793849000}]}]}`. Write updates atomically. The server matches an existing webhook thread, deduplicates event IDs and displays the source session link. The thread status identifies the read mirror, and follow-up messages stay local. A mirror proves a read-backed reply; the mirror provides neither live outbound multi-turn delivery nor automatic browser authentication. With Compose, put the file in the workspace volume and set the path under `/data`.

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

## Recovery and cleanup

The server serializes concurrent replies and persists request IDs, so duplicate client submissions keep the original thread. Mappings survive process restarts. A remote timeout leaves an uncertain delivery visible; the server requires an operator check before any replacement work. Check the upstream history before starting a replacement thread.

Keep the published listener on loopback; there is no login or authorization between named colleagues. The JSON API rejects cross-origin browser writes. The Alertmanager endpoint requires its separate shared secret. API and webhook credentials remain inside the server process and never appear in state responses.

Run `make -C demo-platform/collection check test` for syntax checks and API-fixture integration tests. Stop with `make -C demo-platform/collection mock-down`. Add `-v` to the underlying Compose down command only when discarding recorded threads is intended. Revoke temporary keys and delete their stored secrets when the collection no longer needs live triggering.
