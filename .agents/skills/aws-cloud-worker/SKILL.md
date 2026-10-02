---
name: aws-cloud-worker
description: >
  Repo-specific mechanics for answering the OtterWorks CloudWatch DLQ page as
  the AWS engineer on the team. Covers the demo-cloud-worker branch, the
  observer and builder roles, where the alarm, queues, logs, Helm history and
  the git source of truth live, the restore with make cw-apply, the DLQ
  redrive, the after gate, the fix pull request, the CloudTrail close and the
  paths a session leaves alone.
---

# AWS cloud worker on OtterWorks

This skill backs the `!aws_cloud_worker` playbook and the persona sessions of the `aws-cloud-worker` demo. Every command a session needs is on this page. The harness lives in `cloudworker/`, the fault and both gates are recorded in `cloudworker/scenario.yaml`, and the demo runs in the `cloud-worker` tenant (namespace `otterworks-cloud-worker`, web host `t-cloud-worker.demo.otterworks.app`, API host `api-t-cloud-worker.demo.otterworks.app`) in `us-east-1` on cluster `otterworks-dev`.

The event path runs from `file-service` to SNS topic `otterworks-cw-events`, then to SQS queue `otterworks-cw-notifications`, then to `notification-service`, which writes DynamoDB table `otterworks-cw-notifications`. After 3 failed receives a message moves to DLQ `otterworks-cw-notifications-dlq`. Alarm `otterworks-cw-notifications-dlq-depth` goes to `ALARM` when the DLQ holds 1 message or more, and EventBridge rule `otterworks-cw-dlq-alarm-to-devin` posts the page to the Devin webhook.

## 1. Branch

Work from the `demo-cloud-worker` branch for every read and every change, and never check out, branch from, push to or open a pull request against `main`.

```bash
git fetch origin demo-cloud-worker
git checkout -B demo-cloud-worker origin/demo-cloud-worker
```

## 2. Roles and kubeconfig

Every AWS and Kubernetes call in a session runs under one of two demo roles. The machine may carry other AWS credentials in its environment; leave those unused. `cloudworker/assume.sh` reads `CW_AWS_ACCESS_KEY_ID`, `CW_AWS_SECRET_ACCESS_KEY`, `CW_OBSERVER_ROLE_ARN` and `CW_BUILDER_ROLE_ARN` from the environment, assumes the role as user `devin-cw-reader`, and prints the `export` lines for the AWS variables. The role session name is `devin-` followed by your Devin session id, so CloudTrail ties each call to this session.

Use the observer role for every read in the session. With `--kubeconfig` the helper also writes a kubeconfig for cluster `otterworks-dev`, where the observer has `view` in `otterworks-cloud-worker` and `otterworks-main`.

```bash
source <(cloudworker/assume.sh observer devin-<session id> --kubeconfig)
aws sts get-caller-identity --query Arn --output text   # assumed-role/devin-cw-observer/devin-<session id>
```

Switch to the builder role only for the restore in step 5 and the redrive in step 6, and switch back to the observer as soon as the redrive has started. The builder adds `edit` in `otterworks-cloud-worker`, the SQS redrive and purge actions on the two demo queues, and `cloudwatch:SetAlarmState` on the demo alarm.

```bash
source <(cloudworker/assume.sh builder devin-<session id> --kubeconfig)
# make cw-apply, then the redrive
source <(cloudworker/assume.sh observer devin-<session id> --kubeconfig)
```

## 3. Status

```bash
make cw-status          # pods, live vs git table, queue and DLQ depth, alarm, helm revisions, armed_at
cloudworker/cw.sh status --json   # the same screen as JSON
```

Run it first and paste the screen into your notes. The live `DYNAMODB_TABLE_NOTIFICATIONS` next to the value in `eventing.env` answers most pages on its own.

## 4. Telemetry and the source of truth

Read in this order, with the observer role, before you open any application code.

The alarm shows when the page fired and why:

```bash
aws cloudwatch describe-alarms --alarm-names otterworks-cw-notifications-dlq-depth \
  --query 'MetricAlarms[0].[StateValue,StateReason,StateUpdatedTimestamp]' --output table
aws cloudwatch describe-alarm-history --alarm-name otterworks-cw-notifications-dlq-depth \
  --history-item-type StateUpdate --max-records 5
```

The queue attributes show where the messages went and how long they are kept. Dashboard `otterworks-cloud-worker` plots the same depths and the age of the oldest message.

```bash
for q in otterworks-cw-notifications otterworks-cw-notifications-dlq; do
  url=$(aws sqs get-queue-url --queue-name "$q" --query QueueUrl --output text)
  aws sqs get-queue-attributes --queue-url "$url" --attribute-names \
    ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible MessageRetentionPeriod RedrivePolicy
done
```

The consumer logs show the exception and the table name it used:

```bash
kubectl -n otterworks-cloud-worker logs deploy/notification-service --since=15m | grep -E 'ResourceNotFoundException|otterworks-cw-notifications'
```

Helm history shows the revision that changed the config, with its time and description:

```bash
helm history -n otterworks-cloud-worker notification-service
kubectl -n otterworks-cloud-worker get configmap notification-service-config -o jsonpath='{.data.DYNAMODB_TABLE_NOTIFICATIONS}{"\n"}'
```

The git source of truth for the tenant's eventing config is `infrastructure/helm/tenant-values/cloud-worker/eventing.env`. Compare its `DDB_NOTIF` with the live value. When the live value differs from git and the git value is the table that exists, the cause is a change applied to the cluster by hand, and the fix is to restore from git. Leave `eventing.env` as it is.

```bash
cat infrastructure/helm/tenant-values/cloud-worker/eventing.env
aws dynamodb describe-table --table-name otterworks-cw-notifications --query 'Table.TableStatus'
```

Helm stores release history in Kubernetes Secrets, and `view` cannot read Secrets. If `helm history` is refused under the observer, record the refusal, use `kubectl -n otterworks-cloud-worker rollout history deploy/notification-service` and the ConfigMap value above, and carry on.

## 5. Restore

Assume the builder role, then:

```bash
make cw-apply
```

`cw-apply` re-renders `notification-service` and `file-service` in `otterworks-cloud-worker` from `eventing.env` with `helm upgrade --reuse-values`, restarts both and waits for the pods to be ready. It is idempotent. Restore before the redrive, so the redriven messages reach a consumer that writes to the right table.

## 6. Redrive

Still under the builder role, move the DLQ back to its source queue:

```bash
DLQ_URL=$(aws sqs get-queue-url --queue-name otterworks-cw-notifications-dlq --query QueueUrl --output text)
DLQ_ARN=$(aws sqs get-queue-attributes --queue-url "$DLQ_URL" --attribute-names QueueArn --query Attributes.QueueArn --output text)
aws sqs start-message-move-task --source-arn "$DLQ_ARN"
aws sqs list-message-move-tasks --source-arn "$DLQ_ARN"   # wait for COMPLETED
```

With no `--destination-arn` the messages go back to `otterworks-cw-notifications`. Switch back to the observer role once the task shows `COMPLETED`.

## 7. Verify

The gate publishes one simulated event, and only the builder role may publish to the demo topic, so run it under the builder role and switch back afterwards.

```bash
source <(cloudworker/assume.sh builder devin-<session id> --kubeconfig)
make cw-verify EXPECT=after
source <(cloudworker/assume.sh observer devin-<session id> --kubeconfig)
```

The gate passes when the live table matches git, the DLQ depth is 0, the alarm is `OK` or `INSUFFICIENT_DATA`, the pods are ready, and one simulated `file_shared` event shows up as an item in `otterworks-cw-notifications` within 90 seconds. The alarm can take a minute or two to leave `ALARM` after the DLQ empties. Re-run the gate after that minute and leave the thresholds alone. Paste the gate output exactly as printed. If a step is still refused, report that step and its error, and say the operator runs the gate.

## 8. Fix pull request

The restore in step 5 ends the incident, and the pull request makes the next bad table name fail at boot, before any message is consumed. Add a startup check to `notification-service` (`services/notification-service/`, Kotlin, Ktor):

- On boot, call DynamoDB `DescribeTable` on the configured `DYNAMODB_TABLE_NOTIFICATIONS` (`AppConfig.dynamoDbTableNotifications`).
- When the table is not found, log one error line that names the table, keep the pod out of readiness, and leave the SQS consumer stopped, so the messages wait in the queue.
- Keep `/health` as the liveness check. Serve readiness from its own path and point the chart's readiness probe at it, so the pod reports unready and does not restart in a loop.
- Add one test that fails readiness for a missing table and passes for a present one.

Run `gradle check --no-daemon` in `services/notification-service` (Gradle 8.6, Java 17, as CI does). The IRSA role `otterworks-cw-notification-service` must allow `dynamodb:DescribeTable` on the table for the check to run in the tenant; if it does not, say so in the pull request body and leave Terraform alone.

Push to a new branch named `demo-cw-<unix ts>-<slug>` and open the pull request against `demo-cloud-worker`:

```bash
git checkout -b "demo-cw-$(date +%s)-table-startup-check" origin/demo-cloud-worker
```

Pushing a `demo-cw-*` branch makes CD deploy it to tenant `cw-<unix ts>-<slug>`. The reset closes these pull requests and tears down those tenants. Nothing from a run merges.

The pull request body carries the cause, the restore and redrive you ran, the `make cw-verify EXPECT=after` output and the test you added. Replace the account number in any ARN with `<account>` before you paste it into the pull request, a commit or the session report.

## 9. CloudTrail close

```bash
make cw-trail
```

`cw-trail` lists the last 2 hours of CloudTrail events by users whose names start with `devin-cw-`, as a table of time, user, event and source. Reads show under `devin-cw-observer` and the redrive under `devin-cw-builder`, each with session name `devin-<session id>`. CloudTrail event history can trail the API call by several minutes.

## 10. Paths and systems to leave alone

- `t-main` and namespace `otterworks-main`, which are read-only context.
- Every tenant other than `cloud-worker`, apart from the `cw-*` tenants CD creates for your own branches.
- The `main` branch.
- The planted bugs that belong to other labs, such as `services/admin-service/config/environments/production.rb` and the document-service flaws described in `.agents/skills/incident-responder/SKILL.md`.
- The harness in `cloudworker/`, including `scenario.yaml` and the gates.
- Terraform, including `infrastructure/terraform/cloud-worker/`, and the alarm, its threshold and the EventBridge rule.
