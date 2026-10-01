# On-call storm automation

The Devin Automation below turns the storm page from Alertmanager into a Devin session with no human prompt in between. Register the automation in the Demo org through the v3 API (`POST /v3/organizations/{org_id}/automations`) or in **Settings** → **Automations**, after the playbook from `.workshop/playbooks/oncall-storm.devin.md` exists in the same org so the `!oncall_storm` macro resolves. The existing incident responder automation (`docs/incident-responder/automation.md`) keeps answering the `page: devin` alerts, and the two automations never see each other's pages because Alertmanager routes `page: oncall` only to the `oncall-devin` receiver.

## Trigger

| Field | Value | Reason |
|---|---|---|
| Event | `webhook:incoming` | Alertmanager posts its v4 JSON to the automation's webhook URL, and the body is appended to the prompt verbatim. |
| Condition | `status eq firing`, applied by the preflight check `incident/oncall/automation/preflight.py` | The API rejects conditions on `webhook:incoming` triggers, so the preflight script reads the body and skips anything other than a firing `page=oncall` group from an `otterworks-oncall-*` namespace. |
| Router side | route `page="oncall"` to receiver `oncall-devin`, `group_by: [namespace, oncall_group]`, `group_wait: 3m`, `group_interval: 6h`, `repeat_interval: 12h`, `send_resolved: false` | The 3 minute wait collects the storm into one notification, and the 6 hour interval keeps later alerts in the same group from paging again during the demo. |

The preflight check was tested as a draft run against a firing group (decision `run`) and a resolved group (decision `skip`, reason `status is 'resolved', not 'firing'`).

## Action

`start_session` with the prompt below. The prompt names the repository with an `@` token, and the `oncall-storm` skill loads from the repository on its own.

```text
!oncall_storm

You have been paged by Alertmanager. The webhook body appended below is one grouped notification for the on-call storm, and nobody will type a follow-up prompt. The paging tenant runs from @Cognition-Partner-Workshops/otterworks and the `oncall-storm` skill in that repository has every command you need.

Follow the !oncall_storm playbook from step 1 to the end. Post to the incident channel at https://incident.demo.otterworks.app with $INCIDENT_CHANNEL_TOKEN, using the groupKey from the payload as the thread id. The PR base is the alert's fix_branch label (demo-oncall-after). Never open a PR against main, never push to demo-oncall-before, and never merge. Keep watching the channel thread after the RCA, act on every SRE reply, and finish only when the incident manager closes the incident.

If the payload status is resolved, post nothing and stop with one line naming the groupKey.
```

The prompt is short because the playbook carries the order of work and the skill carries the commands. `$INCIDENT_CHANNEL_TOKEN` is an org secret holding the same value as `CHANNEL_TOKEN` in `otterworks-platform/incident-channel-secrets`, and AWS credentials for `otterworks-dev` come from the org secrets the other workshop sessions already use.

## Limits

| Setting | Value | Reason |
|---|---|---|
| Concurrency | `max_concurrent_runs: 1`, `max_queue_depth: 0` | Two sessions on one storm would race on the same branch and post twice in the thread, and a queued page would start after the incident is closed. |
| Invocation cap | 3 per 3600 s | Covers a live page, one rehearsal and one replay with `make oncall-simulate` in the same hour, and stops a misrouted receiver from starting a session per alert. |
| ACU limit | 30 per session | The parent session reads telemetry, writes the migration, runs a 10 minute proof and waits on the channel for steering, and each child session spends a few ACUs. |
| Approval | `bypass_approval: true` | The playbook may fan out to two child sessions, and an unattended session cannot answer an approval prompt. |
| Agent mode | Normal | The skill holds the mechanics, so the default mode completes the loop. |

## Validated configuration

The payload below, with the text block above as the `start_session` prompt and the preflight file as its source, passes `validate_create` against the Automations API.

```json
{
  "name": "OtterWorks on-call storm: Alertmanager group page to Devin",
  "run_as": {"type": "organization"},
  "triggers": [{"event_type": "webhook:incoming"}],
  "preflight": {
    "runtime": "python",
    "source": "<contents of incident/oncall/automation/preflight.py>",
    "timeout_seconds": 30
  },
  "actions": [{
    "type": "start_session",
    "prompt": "<the prompt above>",
    "session": {"tags": ["oncall-storm"], "bypass_approval": true}
  }],
  "limits": {
    "max_acu_limit": 30,
    "invocations": {"max_per_window": 3, "window_seconds": 3600}
  },
  "concurrency": {"max_concurrent_runs": 1, "max_queue_depth": 0},
  "session_settings": {"devin_mode": "normal"},
  "notifications": {"email": {"when": "dispatch_failed"}},
  "metadata": {"demo": "oncall-storm", "service": "otterworks-document-service"},
  "enabled": true
}
```

The incident responder automation omits `session_settings.net_policy` because a policy-scoped session on the partner-workshops host gets `403` from the git proxy (see `docs/incident-responder/automation.md`), and this automation omits it for the same reason.

## Alertmanager wiring

Export `ONCALL_DEVIN_WEBHOOK_URL` (the automation's webhook URL) and `ONCALL_DEVIN_WEBHOOK_SECRET` (its one-time secret) in your shell, then run `make oncall-platform-up`. `incident/oncall/platform/merge-alertmanager-routes.py` inserts the `oncall-devin` and `oncall-channel` routes into the live Alertmanager config and sends the secret as an `X-Webhook-Secret` header declared under `http_headers.X-Webhook-Secret.values`. With neither variable set, the route reaches only the incident channel and the demo runs with `make oncall-simulate` driving Devin by hand.

`make oncall-simulate` posts the recorded group (`incident/oncall/fixtures/storm-payload.json`, timestamps moved to now) to the channel, and also to the automation when `ONCALL_DEVIN_WEBHOOK_URL` is set. `incident/oncall/simulate.sh --print` prints the same body for pasting into a session by hand.
