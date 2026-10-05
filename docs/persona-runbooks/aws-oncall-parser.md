# AWS on-call: the parser page

Devin is paged by CloudWatch, finds the commit that broke the consumer, ships the fix and proves the queue is healthy again. Nobody prompts the session: an EventBridge rule posts the alarm to a Devin automation that the AWS persona created, so the session appears on the AWS sidebar on its own.

| Field | Value |
|---|---|
| `runAs` | AWS (`user-094334530455473bb8c587d207307833`) |
| Field Kit | Area `ISV and platform`, Identity `AWS` |
| Delegation shape | Event driven. The same page arrives every time a release breaks the consumer, and the same loop answers it. |
| Repository | `Cognition-Partner-Workshops/otterworks` |
| Release under test | `demo-cw-release-1791186929-strict-parser`, built as image tag `demo-cw-release-1791186929-strict-parser-14ca29e` |
| Harness | `make cw-arm FAULT=parser` and `faults:` in `cloudworker/scenario.yaml`, on `devin/1791187037-cw-parser-fault` until pull request 1806 merges |
| Tenant | `cloud-worker` on cluster `otterworks-dev`, region `us-east-1` |
| Mode | Fusion (set on the automation) |
| Live time | 25 minutes from `make cw-arm` to the after gate, measured 2026-10-05 |

## Preflight, the day before

Run from a checkout of `devin/1791187037-cw-parser-fault` with operator AWS credentials.

1. `make cw-apply`, then `make cw-status`. The apply puts the baseline image and config back when the previous run's fix image is still deployed. Expect `table live` equal to `table git`, `queue 0 visible`, `dlq 0 visible`, `alarm OK, actions enabled`, and the notification-service image at the baseline tag `workshop-ep-contracts-2c2d7ff`. The queue retention reads 1209600 seconds against 345600 in Terraform; that drift is planted on purpose for the discovery act and `cw-arm` leaves it alone.
2. Confirm the automation. In the Devin web app as the AWS persona, open Automations and check that the DLQ automation is owned by AWS, runs as its creator and uses the `aws-cloud-worker` playbook. The EventBridge rule `otterworks-cw-dlq-alarm-to-devin` must be `ENABLED` and point at the API destination `otterworks-cw-devin-webhook`.
3. Check the org secrets exist, by name only: `CW_AWS_ACCESS_KEY_ID`, `CW_AWS_SECRET_ACCESS_KEY`, `CW_OBSERVER_ROLE_ARN`, `CW_BUILDER_ROLE_ARN`. The session assumes `devin-cw-observer` for every read and `devin-cw-builder` for the deploy and the redrive.
4. Read `make cw-trail` once so you know what an empty trail looks like before the session writes to it.

## Live

1. Say what is about to happen: a release of notification-service with a strict JSON parser is going out, and six file-share events are going to hit it.
2. Run `make cw-arm FAULT=parser`. The harness deploys the strict-parser image, publishes six `file_shared` events and prints the harness expectations. The consumer rejects each message, SQS moves them to the DLQ after three receives, and the alarm goes to `ALARM` about five minutes later (08:41:20 to 08:46:14 on 2026-10-05).
3. Switch to the Devin web app as the AWS persona. The session arrives within two minutes of the alarm and shows on the AWS sidebar with the automation badge.
4. Follow the session. Devin reads the consumer logs and the DLQ bodies, names the rejecting line, the commit and the exception, reads the Helm history and the running image tag, changes the parser to accept the SNS envelope fields again (`ignoreUnknownKeys = true` with `isLenient = false`), adds a test, builds and deploys the fixed image under the builder role, redrives the DLQ, runs `make cw-verify EXPECT=after` and opens a pull request against the release branch.
5. Close on the 5/5 after gate, the pull request with its CI checks, and the `make cw-trail` table. The table puts every read under `devin-cw-observer` and the deploy and `StartMessageMoveTask` under `devin-cw-builder`, each tagged with the session id.

## Expected state after

| Check | Expected |
|---|---|
| `make cw-verify EXPECT=after` | `PASS (5/5)` |
| `make cw-status` | `dlq 0 visible`, `alarm OK, actions enabled`, image at the fix tag |
| Pull request | open against `demo-cw-release-1791186929-strict-parser` with CI green; it stays open because merging it removes the planted fault |
| Alarm history | `OK` to `ALARM` after arming, `ALARM` to `OK` after the redrive |

## Reset

After the show, back on the operator machine:

```bash
make cw-apply            # restores the baseline image and config from git
make cw-status           # dlq 0, alarm OK, image workshop-ep-contracts-2c2d7ff
```

Then re-plant the retention drift that `cw-arm` reset so the discovery act still has something to find:

```bash
Q=$(aws sqs get-queue-url --queue-name otterworks-cw-notifications --query QueueUrl --output text)
aws sqs set-queue-attributes --queue-url "$Q" --attributes MessageRetentionPeriod=1209600
```

Leave the pull request open. `make cw-reset` closes every `demo-cw-*` pull request and drops the `cw-*` tenants, so run it only when the whole AWS story is being rebuilt.

## Fallback

- Alarm still `OK` five minutes after arming: run `make cw-status`. With one or more messages in the DLQ, wait for the next 60 second evaluation. With the DLQ at 0, the consumer has not failed yet; read the notification-service pod log.
- Alarm in `ALARM` and no session after two minutes: check `otterworks-cw-events-dlq` for a failed webhook delivery, then start a session by hand as the AWS persona with `!aws_cloud_worker` and the alarm payload from `docs/aws-cloud-worker/automation.md` with `state` set to `ALARM`.
- Session asks for network access to a package registry: approve it from the session page. The 2026-10-05 run needed it once for the Gradle build.

## Talk track

The value is the loop, and the loop is generic: a release breaks a consumer, a metric pages, Devin gets the page, and the fix comes back as a pull request with a before and after gate and an audit trail. The only OtterWorks-specific parts are the queue names. Point at the trail last: every API call Devin made is in CloudTrail under a role session named after the Devin session.

## Evidence from the recorded run

| Item | Where |
|---|---|
| Paged session, owned by AWS, Fusion, triggered by automation | https://partner-workshops.devinenterprise.com/sessions/546a849a377c485ca5d8a5a11d8b0863 |
| Fix pull request, 8 checks passed | https://github.com/Cognition-Partner-Workshops/otterworks/pull/1809 |
| Alarm history, after gate, image tag, retention | `evidence/aws/final-audit-parser-546a.txt` |
| CloudTrail by role session | `evidence/aws/final-audit-cw-trail-546a.txt` |
| Arm transcript | `evidence/aws/cw-arm-parser-aws.log` |

## Rerun log

| Date | Who | Session | What the runbook had not said |
|---|---|---|---|
| 2026-10-05 | AWS persona through the automation | `546a849a` | Approve the network request for Gradle; re-plant the retention drift after `cw-arm`. Both added above. |
| 2026-10-05 | AWS persona through the automation, second run | `d6ebb5e0` | The tenant was still on the previous run's fix image, so the preflight now starts with `make cw-apply`. Armed 15:11:35Z, alarm 15:15:14Z, session 15:15:15Z. |
