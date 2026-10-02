# Cloud worker harness

The scripts in this directory set up, run and reset the `aws-cloud-worker` demo on the shared cluster. A file share goes from file-service to the SNS topic `otterworks-cw-events`. The queue `otterworks-cw-notifications` feeds notification-service, which writes to the DynamoDB table `otterworks-cw-notifications`. When the consumer fails three times, the message moves to `otterworks-cw-notifications-dlq`. The alarm `otterworks-cw-notifications-dlq-depth` then goes to ALARM and EventBridge posts the Devin webhook.

The fault, the drift, the thresholds and both gates are in `scenario.yaml`. The git source of truth for the tenant's eventing config is `infrastructure/helm/tenant-values/cloud-worker/eventing.env`.

## Before you start

You need the AWS CLI, `terraform`, `kubectl`, `helm`, `jq` and `python3`. `gh` is optional. Export the operator's AWS credentials and point `kubectl` at `otterworks-dev`:

```bash
aws eks update-kubeconfig --name otterworks-dev --region us-east-1
```

To wire the real webhook, put its URL and secret in `~/.cw-webhook.json` as `{"url": "...", "secret": "..."}`. Set `CW_WEBHOOK_FILE` to use another path. Without the file, Terraform keeps its placeholder webhook.

## Verbs

Each verb is `cloudworker/cw.sh <verb>` and also `make cw-<verb>`.

| Verb | Make target | Who runs it | What it does |
|---|---|---|---|
| `up` | `make cw-up` | operator | Applies the Terraform, maps the Devin roles, applies the RBAC, plants the retention drift, wires the tenant if it exists, sends one event and watches the DLQ for two minutes |
| `apply` | `make cw-apply` | operator or builder | Sets the eventing keys and IRSA roles from `eventing.env` on notification-service and file-service, then restarts both |
| `credentials` | `make cw-credentials` | operator | Replaces the `devin-cw-reader` access key and writes `.state/devin-cw-reader.json` with mode 600 |
| `arm` | `make cw-arm` | operator | Points notification-service at `otterworks-cw-notifications-v2` and sends six events |
| `status` | `make cw-status` | anyone | Pods, live and git table, queue depths, alarm, helm history, armed and quiet times. `JSON=1` prints JSON |
| `verify` | `make cw-verify EXPECT=before` | anyone | Prints PASS or FAIL per check with the measured value and exits 1 on any FAIL |
| `simulate` | `make cw-simulate COUNT=3` | operator | Publishes `file_shared` events from a seeded owner to a seeded recipient |
| `quiet` | `make cw-quiet MINUTES=10` | operator | Disables the alarm actions and records when the quiet window ends |
| `disarm` | `make cw-disarm` | operator | Quiets the alarm, restores the config, purges both queues, sets the alarm to OK and turns its actions back on |
| `reset` | `make cw-reset` | operator | Disarms, closes `demo-cw-*` pull requests, deletes those branches, removes `cw-*` tenants and plants the drift again |
| `teardown` | `make cw-teardown` | operator | Resets, unmaps the roles, deletes the RBAC and reader keys and destroys the Terraform. Set `TEARDOWN_TENANT=true` to remove tenant `cloud-worker` as well |
| `trail` | `make cw-trail` | operator | Lists CloudTrail events from `devin-cw-*` identities in the last two hours |

## A demo run

1. Run `make cw-up` once per environment, then `make cw-credentials`. Load the four keys in `.state/devin-cw-reader.json` as Devin session secrets.
2. Run `make cw-arm`. The DLQ fills in about two minutes and the alarm fires in about three.
3. Run `make cw-verify EXPECT=before` to confirm the broken state.
4. Devin restores the config with `make cw-apply`, redrives the DLQ and runs `make cw-verify EXPECT=after`.
5. Run `make cw-reset` before the next audience.

## Devin's identities

A Devin session gets AWS access by assuming one of two roles with `assume.sh`. The observer role can read and the builder role can also redrive the DLQ and set the alarm state. Each session passes its own session name, so CloudTrail shows which session made each call:

```bash
source <(cloudworker/assume.sh observer devin-<session id>)
source <(cloudworker/assume.sh builder devin-<session id> --kubeconfig)
```

`assume.sh` reads `CW_AWS_ACCESS_KEY_ID`, `CW_AWS_SECRET_ACCESS_KEY`, `CW_OBSERVER_ROLE_ARN` and `CW_BUILDER_ROLE_ARN`. With `--kubeconfig` it also writes a kubeconfig entry for that identity.

## State and dry runs

The harness caches the Terraform outputs in `.state/outputs.json` after the first read. Delete the file to read them again. The armed and quiet times are in `.state/state.json`. Git ignores the whole `.state/` directory.

Set `CW_DRY_RUN=1` to print every command without running it:

```bash
CW_DRY_RUN=1 cloudworker/cw.sh arm
```
