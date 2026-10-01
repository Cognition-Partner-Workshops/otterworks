# Incident channel

`channel.py` runs `#inc-otterworks`, the chat page the on-call storm demo uses in place of Slack. Alertmanager posts the oncall group to `/alertmanager`, and the page shows one thread per `groupKey` with an alert card that updates in place as the storm grows. The paged Devin session posts into that thread with the channel token, and whoever is on the page replies as the SRE or the incident manager. Each reply goes to the bound Devin session through the v3 messages API with `message_as_user_id` set to the persona's user id.

The server is one file on the Python 3.12 standard library, so the Deployment mounts it from a ConfigMap on `python:3.12-slim` and needs no image build.

## Run it locally

```bash
CHANNEL_TOKEN=dev-token STATE_FILE=/tmp/channel-state.json python3 incident/oncall/channel/channel.py
curl -s -XPOST localhost:8080/alertmanager -H 'Content-Type: application/json' -d @payload.json
curl -s -XPOST localhost:8080/api/threads/latest/messages \
  -H 'Authorization: Bearer dev-token' -H 'Content-Type: application/json' \
  -d '{"author": "Devin", "text": "Picked up the page.", "session_id": "devin-123", "org_id": "org-123"}'
```

The page is at `http://localhost:8080/`, and pointing `DEVIN_API_BASE` at a local server shows the forwarded replies without touching the real API.

```bash
python3 -m pytest incident/oncall/channel -q
```

## Endpoints

| Method and path | Auth | Purpose |
| --- | --- | --- |
| `POST /alertmanager` | NetworkPolicy, plus the bearer token if the request came through the ingress | Alertmanager v4 webhook. The first payload for a `groupKey` opens the thread and later payloads update the same card. |
| `POST /api/threads/{groupKey}/messages` | `Authorization: Bearer $CHANNEL_TOKEN` | Devin posts a message. `session_id` and `org_id` bind the thread to the session, and image URLs in `attachments` render inline. `{groupKey}` also takes the thread id or `latest`. |
| `POST /api/threads/{groupKey}/reply` | nginx basic auth | The page posts `{"persona": "sre" or "incident-manager", "text": ...}`. The channel forwards `{"message": text, "message_as_user_id": id}` to `$DEVIN_API_BASE/v3/organizations/{org_id}/sessions/{session_id}/messages` and records the status code for the tick under the reply. |
| `POST /api/reset` | bearer token | Clears every thread. |
| `GET /api/state` | nginx basic auth | Thread data and rendered HTML. The page polls every 2 s with `?since=<version>` and gets a short body when the version is unchanged. |
| `GET /healthz` | none | Readiness and liveness. |

A reply shows a green tick with "Delivered to Devin" on a 2xx and a red one with the HTTP status otherwise. When the thread has no bound session yet, or the persona's user id is unset, the channel keeps the reply on the page and shows the reason under it in red.

## Configuration

| Variable | Default | Source |
| --- | --- | --- |
| `CHANNEL_TOKEN` | unset (token routes answer 503) | Secret `incident-channel-secrets` |
| `DEVIN_API_KEY` | unset (replies are not sent) | Secret `incident-channel-secrets` |
| `DEVIN_API_BASE` | `https://partner-workshops.devinenterprise.com/api` | plain env |
| `PERSONA_SRE_NAME`, `PERSONA_IM_NAME` | `SRE (on call)`, `Incident manager` | plain env |
| `PERSONA_SRE_USER_ID`, `PERSONA_IM_USER_ID` | unset | plain env, set by `up.sh` |
| `GRAFANA_URL`, `GRAFANA_DASHBOARD_UID` | `https://grafana.otterworks.app`, `oncall-storm` | plain env |
| `ALERTMANAGER_URL` | `https://alertmanager.otterworks.app` | plain env |
| `STATE_FILE` | `/data/state.json` (emptyDir) | plain env |
| `BASIC_AUTH_PASSWORD` | unset | optional second check in the app; nginx already does basic auth on the cluster |

The API key goes out only in the `Authorization` header of the forward. Logs record the session id, persona, status code and latency, and the state the page reads stores the status code alone.

## Deploy

```bash
kubectl apply -k incident/oncall/channel
```

The kustomization next to `channel.py` generates the `incident-channel-script` ConfigMap from the file (kustomize loads files only at or below its own directory) and applies the manifests in `k8s/`: a single-replica Deployment with a `Recreate` strategy so one pod owns the snapshot, a ClusterIP Service on 8080, two Ingress objects for `incident.demo.otterworks.app`, and a NetworkPolicy. The `incident-channel` Ingress puts nginx basic auth from `incident-channel-basic-auth` in front of everything and asks cert-manager (`letsencrypt-prod`) for `incident-channel-tls`. The `incident-channel-api` Ingress carries the two bearer routes with no basic auth and reuses that certificate. The NetworkPolicy admits Alertmanager pods from `monitoring` and the ingress controller on port 8080. Editing `channel.py` changes the ConfigMap hash, so the next apply rolls the pod.
