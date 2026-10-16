# Cloud worker harness

The scripts in this directory set up, run and reset the `aws-cloud-worker` demo on the shared cluster. A file share goes from file-service to the SNS topic `otterworks-cw-events`. The queue `otterworks-cw-notifications` feeds notification-service. The service reads each recipient's preferences from `otterworks-cw-notification-preferences` and writes to `otterworks-cw-notifications`. When the consumer fails three times, the message moves to `otterworks-cw-notifications-dlq`. The alarm `otterworks-cw-notifications-dlq-depth` then goes to ALARM and EventBridge posts the Devin webhook.

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
| `up` | `make cw-up` | operator | Applies the Terraform, maps the Devin roles, applies the RBAC, adds the tenant's two hosts to external-dns's domain filters (perpetual tenants sit at the apex, outside the `demo.` filter), plants the retention drift, wires the tenant if it exists, sends one event and watches the DLQ for two minutes |
| `apply` | `make cw-apply` | operator or builder | Sets the eventing keys, including the preferences table, and IRSA roles from `eventing.env` on notification-service and file-service, then restarts both |
| `credentials` | `make cw-credentials` | operator | Replaces the `devin-cw-reader` access key and writes `.state/devin-cw-reader.json` with mode 600 |
| `arm` | `make cw-arm` | operator | Plants a fault from the `faults:` map in `scenario.yaml`, sends six events and clears any quiet window. The default, `table`, points notification-service at `otterworks-cw-notifications-v2`. `FAULT=parser` keeps the config equal to git, sets the queue retention to the Terraform value and rolls the strict-parser release image. `PAGE=0` leaves the EventBridge rule as it is |
| `status` | `make cw-status` | anyone | Pods, live and git table, queue depths, queue retention against Terraform, running notification-service image, alarm, EventBridge rule state, helm history, armed fault and time, quiet time. `JSON=1` prints JSON |
| `verify` | `make cw-verify EXPECT=before` | anyone | Prints PASS or FAIL per check with the measured value and exits 1 on any FAIL. Pass `FAULT=parser` with `EXPECT=before` for the parser gate; `EXPECT=after` is the same for both faults |
| `simulate` | `make cw-simulate COUNT=3` | operator | Publishes `file_shared` events from a seeded owner to a seeded recipient |
| `quiet` | `make cw-quiet MINUTES=10` | operator | Disables the alarm actions and the EventBridge rule, and records when the quiet window ends; `arm` and `disarm` turn both back on |
| `disarm` | `make cw-disarm` | operator | Quiets the alarm, restores the config and the image recorded at `arm`, purges both queues, sets the alarm to OK and turns its actions back on. It turns the rule back on once a DLQ datapoint after the purge reads 0, because the forced `OK` flips back to `ALARM` on the last full minute and would page. `PAGE=0` leaves the rule as it is |
| `reset` | `make cw-reset` | operator | Disarms, closes `demo-cw-*` pull requests, deletes those branches, removes `cw-*` tenants and plants the drift again. `demo-cw-release-*` branches are kept, so the parser image keeps its source. `SCOPE=run` limits the cleanup to branches and tenants whose timestamp is at or after `armed_at`, for a rehearsal on a cluster other sessions share |
| `teardown` | `make cw-teardown` | operator | Resets, unmaps the roles, deletes the RBAC and reader keys and destroys the Terraform. Set `TEARDOWN_TENANT=true` to remove tenant `cloud-worker` as well |
| `trail` | `make cw-trail` | operator | Lists CloudTrail events from `devin-cw-*` identities in the last two hours |

## A demo run

1. Run `make cw-up` once per environment, then `make cw-credentials`. Load the four keys in `.state/devin-cw-reader.json` as Devin session secrets.
2. Run `make cw-arm`. The DLQ fills in about two minutes and the alarm fires in about three.
3. Run `make cw-verify EXPECT=before` to confirm the broken state.
4. Devin restores the config with `make cw-apply`, redrives the DLQ and runs `make cw-verify EXPECT=after`.
5. Run `make cw-reset` before the next audience.

## The parser fault

`make cw-arm FAULT=parser` is the code-cause variant. It needs `python3` with PyYAML, as every verb now reads `scenario.yaml`. The fault's `image_tag` names an image CD built from release branch `demo-cw-release-1791186929-strict-parser` (commit `14ca29e`), which makes the strict JSON parser in `SqsConsumer.kt` the only parser and drops the Redis switch that used to turn it on. `arm` looks the tag up in ECR and pins it by digest; it stops if the image is missing. The before gate is `make cw-verify EXPECT=before FAULT=parser`: config equal to git, DLQ at least 1, alarm `ALARM`, and a `Failed to parse SQS message` line in the last 15 minutes of logs. `disarm` and `reset` put the image recorded at the first `arm` back, so the golden image runs again afterward.

To build a new release image, branch `demo-cw-release-<unix ts>-<slug>` from `demo-cloud-worker`, make the change, push, read the tag from the CD run (`demo-cw-release-<unix ts>-<slug>-<short sha>`), set `faults.parser.image_tag` and the answer key in `scenario.yaml`, and tear down the tenant CD made with `scripts/teardown-tenant.sh cw-release-<unix ts>-<slug>`. Never push the release change to `demo-cloud-worker`.

## Devin's identities

A Devin session gets AWS access by assuming one of two roles with `assume.sh`. The observer role can read and the builder role can also redrive the DLQ and set the alarm state. Each session passes its own session name, so CloudTrail shows which session made each call:

```bash
source <(cloudworker/assume.sh observer devin-<session id>)
source <(cloudworker/assume.sh builder devin-<session id> --kubeconfig)
```

`assume.sh` reads `CW_AWS_ACCESS_KEY_ID`, `CW_AWS_SECRET_ACCESS_KEY`, `CW_OBSERVER_ROLE_ARN` and `CW_BUILDER_ROLE_ARN`. With `--kubeconfig` it also writes a kubeconfig entry for that identity.

## State and dry runs

The harness caches the Terraform outputs in `.state/outputs.json` after the first read. Delete the file to read them again. The armed fault, the armed and quiet times and the baseline image are in `.state/state.json`. Git ignores the whole `.state/` directory.

Set `CW_DRY_RUN=1` to print every command without running it:

```bash
CW_DRY_RUN=1 cloudworker/cw.sh arm
```
