# AWS cloud worker automation

The Devin Automation `aws-cloud-worker-dlq-alarm` turns the CloudWatch DLQ alarm into a Devin session with no human prompt in between. It runs act 2 of the demo. The session follows `.workshop/playbooks/aws-cloud-worker.devin.md` and takes its commands from `.agents/skills/aws-cloud-worker/SKILL.md`.

Register the Playbook and the Automation in the Demo org (`org-012fdeb7967c4e399b9d71cf5c857b63`) for rehearsal, and in Partner Demo - ViewOnly (`org-2c583a9e9aee4e02ad076bb48afe8dc9`) for the target run. Use **Settings** → **Automations** or the v3 API `POST /v3/organizations/{org_id}/automations`. Register the Playbook first, since the prompt names it by id.

## Alarm to webhook

```text
SQS otterworks-cw-notifications-dlq (ApproximateNumberOfMessagesVisible)
  CloudWatch alarm otterworks-cw-notifications-dlq-depth (Sum, 60 s, 1 of 1, >= 1, missing data not breaching)
    EventBridge default bus, rule otterworks-cw-dlq-alarm-to-devin
      API destination otterworks-cw-devin-webhook (POST, 1 request per second)
        connection otterworks-cw-devin-webhook (API_KEY, header X-Webhook-Secret)
          Devin Automation aws-cloud-worker-dlq-alarm (webhook:incoming)
```

EventBridge rule `otterworks-cw-dlq-alarm-to-devin` on the default bus matches events with `source` `aws.cloudwatch`, `detail-type` `CloudWatch Alarm State Change`, `detail.alarmName` `otterworks-cw-notifications-dlq-depth` and `detail.state.value` `ALARM`. A return to `OK` sends nothing. The alarm carries no alarm actions, so EventBridge is the only path to Devin.

The rule's target is the API destination, invoked with role `otterworks-cw-eventbridge-invoke`. EventBridge retries a failed delivery 2 times within a maximum event age of 300 seconds, then moves the event to `otterworks-cw-events-dlq`. When a page fails to start a session, read that queue first.

The input transformer sends this body, and the Automation appends the body to the prompt:

```json
{
  "source": "cloudwatch-alarm",
  "alarm": "<detail.alarmName>",
  "state": "<detail.state.value>",
  "reason": "<detail.state.reason>",
  "time": "<time>",
  "region": "<region>",
  "account": "<account>",
  "tenant": "cloud-worker",
  "namespace": "otterworks-cloud-worker",
  "branch": "demo-cloud-worker",
  "service": "notification-service",
  "queue": "otterworks-cw-notifications",
  "dlq": "otterworks-cw-notifications-dlq",
  "dashboard": "otterworks-cloud-worker"
}
```

## Connecting EventBridge to the Automation

Create the Automation, then copy its incoming webhook URL and its one-time secret into `~/.cw-webhook.json` on the operator machine. `make cw-up` reads that file (or the path in `CW_WEBHOOK_FILE`) and passes the values to Terraform as `TF_VAR_devin_webhook_url` and `TF_VAR_devin_webhook_secret`. Keep the file mode 600 and out of git.

```json
{"url": "<incoming webhook URL>", "secret": "<webhook secret>"}
```

Without the file, Terraform uses the defaults `https://example.invalid/webhook` and `replace-me`, and the page goes nowhere. Re-run `make cw-up` after you rotate the secret.

## Settings

| Setting | Value | Reason |
|---|---|---|
| Name | `aws-cloud-worker-dlq-alarm` | Named in the interface spec and the reset. |
| Trigger | one `webhook:incoming` | EventBridge posts the alarm, and no person types the page. |
| Action | one `start_session` | One page starts one session. |
| Prompt | `@playbook:<id> !aws_cloud_worker` | Replace `<id>` with the Playbook id from the org you registered it in. The skill carries the commands. |
| Approval | `bypass_approval` | The session starts unattended while the presenter talks. |
| ACU limit | 30 per session | Covers diagnose, restore, redrive, verify and the pull request, and caps a runaway loop. |
| Invocations | 3 per hour | A stuck alarm or a re-arm cannot start a session every few minutes. |
| Concurrency | 1 running, queue 0 | A second page during a run is dropped. A queued run would start after the incident is over. |
| Mode | `fusion` | The record asks for fusion on every act. |
| Run as | `run_as: organization` | The org automation user owns the act 2 session. Acts 1 and 3 carry the persona user ids. |
| Tags | `aws-cloud-worker`, `req-2026-10-01-008` | The same tags as the persona sessions, so the run is found in one search. |

The session needs the four `CW_*` secrets described in `runbook.md` as org secrets in the org that runs it. The repository is `Cognition-Partner-Workshops/otterworks`.

## Configuration record

This record copies the field layout of the validated incident responder record in `docs/incident-responder/automation.md`. It has not been validated against the Automations API yet. Run `validate_create` with it before you register.

```json
{
  "name": "aws-cloud-worker-dlq-alarm",
  "run_as": {"type": "organization"},
  "triggers": [{"event_type": "webhook:incoming"}],
  "actions": [{
    "type": "start_session",
    "prompt": "@playbook:<id> !aws_cloud_worker",
    "session": {"tags": ["aws-cloud-worker", "req-2026-10-01-008"], "bypass_approval": true}
  }],
  "limits": {
    "max_acu_limit": 30,
    "invocations": {"max_per_window": 3, "window_seconds": 3600}
  },
  "concurrency": {"max_concurrent_runs": 1, "max_queue_depth": 0},
  "session_settings": {"devin_mode": "fusion"},
  "metadata": {"demo": "aws-cloud-worker", "request": "req-2026-10-01-008"},
  "enabled": true
}
```

## Testing the path

Use `make cw-arm` to test the real path, since it changes the config and waits for the alarm. To test only EventBridge and the webhook, set the alarm state by hand with the operator's credentials. EventBridge sees the change and posts the payload.

```bash
aws cloudwatch set-alarm-state --alarm-name otterworks-cw-notifications-dlq-depth \
  --state-value ALARM --state-reason "manual webhook test"
```

The session then finds an empty DLQ and a live table that matches git, and reports that. Run `make cw-disarm` afterward to set the alarm back to `OK`. Each test counts against the 3 per hour cap.
