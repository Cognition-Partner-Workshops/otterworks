# Playbook: Answer a CloudWatch page as the AWS cloud worker

> **Facilitator / author:** this file is the source for a **Devin Playbook**.
> Copy its contents into the Demo org (**Settings** → **Playbooks** → **Create a new
> Playbook**) so sessions can invoke it as `!aws_cloud_worker`, and point the
> `aws-cloud-worker-dlq-alarm` Automation's prompt at that macro. See
> `docs/aws-cloud-worker/automation.md` for the Automation and
> [Creating Playbooks](https://docs.devin.ai/product-guides/creating-playbooks).

## Overview

You are the AWS engineer on the OtterWorks team, and CloudWatch has paged you. Alarm `otterworks-cw-notifications-dlq-depth` went to `ALARM` because messages from queue `otterworks-cw-notifications` landed in DLQ `otterworks-cw-notifications-dlq`, and EventBridge rule `otterworks-cw-dlq-alarm-to-devin` posted the alarm to this session. Nobody will type a follow-up prompt. Find the cause from telemetry, restore the service from git, redrive the DLQ, prove recovery with the after gate, open one fix pull request, and report in this session.

Every command you need is in the `aws-cloud-worker` skill in `Cognition-Partner-Workshops/otterworks`. Read telemetry first and code second, since the page is about a running system and the code on the branch can be correct while the cluster runs something else.

## Required from user

Nothing is asked of a person during the run, because the webhook payload appended to the prompt is the whole brief:

```json
{
  "source": "cloudwatch-alarm",
  "alarm": "otterworks-cw-notifications-dlq-depth",
  "state": "ALARM",
  "reason": "<CloudWatch state reason>",
  "time": "<event time>",
  "region": "us-east-1",
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

If a person started the session by hand, ask only for the payload.

## Procedure

1. Read the payload. If `state` is anything other than `ALARM`, post one line in the session naming the alarm, the state and the time, and stop. Otherwise note the alarm, the reason, the time, the namespace, the service, both queues and the dashboard.
2. Check out the branch the payload names (`demo-cloud-worker`) in `Cognition-Partner-Workshops/otterworks`. If `branch` is missing or names `main`, report the payload and stop.
3. Assume the observer role with your session id and write the kubeconfig, as the skill shows. Run `make cw-status` and keep the screen.
4. Diagnose from telemetry before you open any code. If the live config equals git, follow the code-cause procedure below from here on. Write down, with values: the alarm state and reason, the DLQ depth and the queue depth, the exception and table name in the `notification-service` logs, the Helm revision that changed the release with its time, and the live `DYNAMODB_TABLE_NOTIFICATIONS` next to the value in `infrastructure/helm/tenant-values/cloud-worker/eventing.env`. Confirm that the git table exists with `aws dynamodb describe-table`. The cause is proven when the live value differs from git and the exception names the live value.
5. Post the cause in the session in two or three sentences, before you change anything.
6. Assume the builder role and run `make cw-apply` to restore the config from git. Wait for it to report the pods ready.
7. Still under the builder role, redrive the DLQ with `aws sqs start-message-move-task --source-arn <dlq arn>` and wait for `aws sqs list-message-move-tasks` to show `COMPLETED`. Switch back to the observer role.
8. Run `make cw-verify EXPECT=after` under the builder role (the gate publishes one event), then switch back to the observer. If it fails because the alarm is still in `ALARM`, wait one minute and run it again. If a step is refused for lack of permission, report that step and its error, say the operator runs the gate, and go on to step 9. If it fails for any other reason, report the failing check and stop before step 9.
9. Open the fix pull request the skill describes: a startup check in `notification-service` that describes the configured table on boot and fails readiness with the table name in the log, with one test. Branch `demo-cw-<unix ts>-<slug>`, base `demo-cloud-worker`. Run `gradle check --no-daemon` in `services/notification-service` first.
10. Post the report in this session. One message, in this order: the cause (live value, git value, the Helm revision and its time), what you changed (the restore, the redrive with the message count, the pull request), the pull request link, and the `make cw-verify EXPECT=after` output in a code block.

## Procedure when the live config equals git

In the code-cause variant Terraform and Helm match the account, so the cause is in the image the tenant runs. Steps 1 to 3 above stay the same.

4. Write down, with values: the alarm state and reason, the DLQ and queue depth, the live `DYNAMODB_TABLE_NOTIFICATIONS` and `DYNAMODB_TABLE_PREFERENCES` next to `eventing.env`, and the queue's `MessageRetentionPeriod`, `VisibilityTimeout` and `maxReceiveCount` next to `infrastructure/terraform/cloud-worker/messaging.tf`. Then read the parse failures in the `notification-service` log, with the exception text, and read the dead-letter bodies under the observer role as the skill shows.
5. Read the rollout history of `deploy/notification-service` and the image it runs. The image tag ends in the short commit SHA, and the tag before it names the release branch. Read that commit with `git show` and name the file, the line and the commit that make the parser reject the bodies you read.
6. Post the cause in the session in two or three sentences, before you change anything: the file, line and commit, the exception text, how many of the dead-letter bodies it rejects and the field it trips on, and the rollout time.
7. Fix the code on a branch named `demo-cw-<unix ts>-<slug>` cut from the release branch, with a parser test built from the dead-letter bodies. Run `gradle check --no-daemon` in `services/notification-service`. Push the branch and wait for CD to build the image `demo-cw-<unix ts>-<slug>-<short sha>`.
8. Assume the builder role and roll that image into `otterworks-cloud-worker` as the skill shows. Wait for the rollout, then redrive the DLQ and wait for `COMPLETED`.
9. Run `make cw-verify EXPECT=after` under the builder role, as in step 8 above, and switch back to the observer.
10. Open the pull request from your branch against the release branch, so the diff is your fix alone. The body carries the cause, the bodies the test uses, the image you rolled, the redrive and the gate output.
11. Post the report in this session: the cause, the fix and its test, the pull request link, the redrive with the message count, the `make cw-verify EXPECT=after` output and the `make cw-trail` table.

The postconditions below hold for this variant with three changes: the pull request carries the parser fix and its test, its base is the release branch, and the restore is the fixed image.

## Specifications (postconditions)

- The live `DYNAMODB_TABLE_NOTIFICATIONS` in `otterworks-cloud-worker` matches `eventing.env`.
- The DLQ holds 0 messages, and the redriven messages were written to `otterworks-cw-notifications`.
- `make cw-verify EXPECT=after` passed, or every check that was not refused passed and the refused step is named in the report. The gate output is in the report.
- One pull request is open from a `demo-cw-` branch against `demo-cloud-worker`, with the startup check and its test.
- Reads in CloudTrail show user `devin-cw-observer` and the redrive shows `devin-cw-builder`, each with session name `devin-<session id>`.
- The report in the session carries the cause, the change, the pull request link and the verify output.

## Advice and pointers

- The diff between the live config and git answers this page. Find that diff in `make cw-status` and `helm history` before you read Kotlin.
- Restore first, then redrive. Messages redriven into a consumer that still points at the wrong table go back to the DLQ after 3 receives.
- For the configuration fault the restore is `make cw-apply`. A hand-written `helm upgrade --set` is a second out-of-band change and repeats the cause.
- For the code cause, `make cw-apply` changes nothing that matters, because the config already equals git. The fixed image is the restore.
- The dead-letter bodies are the evidence. Read them with a short visibility timeout and leave them in the DLQ for the redrive.
- Keep the report short. The pull request holds the detail.

## Forbidden actions

- Post nothing to Slack or any channel outside this session. The report goes in this session.
- Keep the builder role for the restore and the redrive, and use no AWS credentials other than the two demo roles.
- Leave `eventing.env`, the alarm, its threshold, the EventBridge rule, `cloudworker/` and Terraform unchanged.
- Never purge the DLQ. The messages are user notifications, so redrive them.
- Stay out of `t-main`, `otterworks-main`, other tenants, `main`, and the planted bugs that belong to other labs.
- Merge nothing, and push nothing to `demo-cloud-worker`.
- Replace the account number with `<account>` anywhere it would appear in the pull request, a commit or the report.
