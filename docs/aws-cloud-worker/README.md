# AWS cloud worker demo

Devin works as the AWS engineer on the OtterWorks team: asked about the account, paged by CloudWatch and handed a change, in ten minutes. The demo runs on branch `demo-cloud-worker`, tenant `cloud-worker` (namespace `otterworks-cloud-worker`) and cluster `otterworks-dev` in `us-east-1`, under request `req-2026-10-01-008`.

## Documents

| File | Read it when |
|---|---|
| [runbook.md](runbook.md) | You run the demo: pre-flight, the prompts for each act, timings, the cut line and the reset. |
| [talk-track.md](talk-track.md) | You present: the opening and one line per act. |
| [automation.md](automation.md) | You register or debug the Automation and the EventBridge path from the alarm to Devin. |
| [discovery-questions.md](discovery-questions.md) | You prepare for the meeting and choose which acts to stress. |
| [objection-handling.md](objection-handling.md) | You answer pushback after the demo. |

## Devin configuration

| File | Purpose |
|---|---|
| `.agents/skills/aws-cloud-worker/SKILL.md` | Every command a session runs: roles, status, telemetry, restore, redrive, verify, the fix pull request, the CloudTrail close and the paths to leave alone. |
| `.workshop/playbooks/aws-cloud-worker.devin.md` | Source of the `!aws_cloud_worker` Playbook, the act 2 procedure for the webhook payload. |

## Harness and infrastructure

| Path | Purpose |
|---|---|
| `cloudworker/` | The harness behind the `make cw-*` targets, the role helper `assume.sh` and the fault record `scenario.yaml`. |
| `infrastructure/terraform/cloud-worker/` | The demo's SNS topic, queues, table, IAM roles, alarm, dashboard and EventBridge rule. |
| `infrastructure/helm/tenant-values/cloud-worker/eventing.env` | The git source of truth for the tenant's eventing config. |

## Make targets

| Target | Does |
|---|---|
| `make cw-up` | Applies the demo infrastructure and prepares the tenant. |
| `make cw-credentials` | Writes a fresh access key for `devin-cw-reader`. |
| `make cw-status` | Prints the tenant, config, queue and alarm state on one screen. |
| `make cw-arm` | Plants the act 2 fault and publishes six events. |
| `make cw-verify EXPECT=before` | Passes while the fault is live. |
| `make cw-apply` | Restores the tenant's eventing config from git. |
| `make cw-verify EXPECT=after` | Passes once the service has recovered. |
| `make cw-trail` | Lists the last 2 hours of CloudTrail calls by the Devin roles. |
| `make cw-quiet MINUTES=10` | Holds the alarm actions off while you rehearse. |
| `make cw-disarm` | Stops a run and restores the baseline. |
| `make cw-reset` | Disarms, closes run pull requests and tears down run tenants. |
| `make cw-teardown` | Resets and removes the demo infrastructure. |
