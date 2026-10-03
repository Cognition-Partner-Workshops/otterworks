# AWS cloud worker runbook

This runbook takes the operator through the `aws-cloud-worker` demo: one AWS engineer persona asks Devin about the account, CloudWatch pages Devin, a product manager hands Devin a change, and CloudTrail shows what Devin did. The demo runs on branch `demo-cloud-worker` and tenant `cloud-worker` (namespace `otterworks-cloud-worker`) in `us-east-1` on cluster `otterworks-dev`.

## Contents

- [Pre-flight](#pre-flight)
- [Act 1: ask](#act-1-ask)
- [Act 2: page](#act-2-page)
- [Act 3: change](#act-3-change)
- [Act 4: close](#act-4-close)
- [Timings](#timings)
- [Cut line](#cut-line)
- [Reset](#reset)

<a id="pre-flight"></a>
## Pre-flight

Run these on the operator machine with your AWS admin credentials, from a checkout of `demo-cloud-worker`, at least 30 minutes before the audience arrives.

1. Check out tenant `cloud-worker` from the ops dashboard as a perpetual tenant tracking `demo-cloud-worker` (`demo-platform/scripts/tenant.sh checkout cloud-worker demo-cloud-worker never`; the dashboard allows it because `perpetualTenantIds` in `demo-platform/helm/demo-platform/values.yaml` lists `cloud-worker`). Open `https://t-cloud-worker.otterworks.app` and sign in.
2. Register the Playbook from `.workshop/playbooks/aws-cloud-worker.devin.md` and the Automation from `automation.md` in the org you are presenting from. Save the Automation's webhook URL and secret to `~/.cw-webhook.json`.
3. Run `make cw-up`. It applies the Terraform in `infrastructure/terraform/cloud-worker/`, maps the Devin roles into the cluster, plants the retention drift for act 1, restores the tenant config and sends one test event. It ends when the DLQ stays at 0.
4. Create the reader key with `make cw-credentials`, which writes a fresh access key for `devin-cw-reader` to `cloudworker/.state/devin-cw-reader.json`. Store the key id and secret as org secrets `CW_AWS_ACCESS_KEY_ID` and `CW_AWS_SECRET_ACCESS_KEY`, and the Terraform outputs `devin_observer_role_arn` and `devin_builder_role_arn` as `CW_OBSERVER_ROLE_ARN` and `CW_BUILDER_ROLE_ARN`.
5. Confirm the baseline with `make cw-status`. Expect the pods ready, the live table equal to the git table, both queues at 0 and the alarm `OK` or `INSUFFICIENT_DATA`.
6. Open CloudWatch dashboard `otterworks-cloud-worker` in a browser tab, and the Demo org session list in another.

```bash
terraform -chdir=infrastructure/terraform/cloud-worker output -raw devin_observer_role_arn
terraform -chdir=infrastructure/terraform/cloud-worker output -raw devin_builder_role_arn
```

<a id="act-1-ask"></a>
## Act 1: ask

Sign in to Devin as the `aws` persona through Field Kit SSO, or create the session through the API with `create_as_user_id` set to the `aws` persona, in fusion mode, with tags `aws-cloud-worker` and `req-2026-10-01-008`. Select repository `Cognition-Partner-Workshops/otterworks` and paste the prompt.

```text
What runs in the demo tenant, how does a file share become a notification, and does the account match Terraform?
```

Devin is done when it has named the path from SNS topic `otterworks-cw-events` to queue `otterworks-cw-notifications` to `notification-service` to DynamoDB table `otterworks-cw-notifications`, the IRSA roles `otterworks-cw-notification-service` and `otterworks-cw-file-service`, and the retention drift. The queue keeps messages for 14 days (1209600 seconds) and Terraform says 4 days (345600 seconds). Keep this session open for act 4.

<a id="act-2-page"></a>
## Act 2: page

Start act 2 while act 1 is still running, so the alarm fires during act 1.

```bash
make cw-arm
```

`cw-arm` points `notification-service` at table `otterworks-cw-notifications-v2`, which does not exist, and publishes six `file_shared` events. The consumer fails on each message, SQS moves each one to the DLQ after 3 receives, and the alarm goes to `ALARM`. EventBridge posts the page, and a session tagged `aws-cloud-worker` appears in the session list under the organization's automation user.

Once the alarm shows `ALARM` on the dashboard, and before Devin restores the config, you can run the before gate as proof that the fault is live. The gate only reads.

```bash
make cw-verify EXPECT=before
```

Open the act 2 session and follow it. Devin posts the cause (the live table differs from `infrastructure/helm/tenant-values/cloud-worker/eventing.env`), runs `make cw-apply` under `devin-cw-builder`, redrives the DLQ, runs `make cw-verify EXPECT=after`, opens a pull request against `demo-cloud-worker` that adds a startup table check to `notification-service`, and posts the report. Act 2 ends when the after gate passes and the report is in the session.

<a id="act-3-change"></a>
## Act 3: change

Sign in to Devin as the `product-manager` persona, or create the session with `create_as_user_id` set to that persona, in fusion mode, with the same tags. Paste the prompt.

```text
I'm the product manager for the OtterWorks admin dashboard in Cognition-Partner-Workshops/otterworks. On the dashboard overview, add a "Signed in today" tile with the number of users who signed in today, and add a "Last sign-in" column to the users table. Update the admin API docs for any admin endpoint you add or change. Deploy it somewhere I can open in a browser and send me the link. Work from the demo-cloud-worker branch, push to a new branch named demo-cw-<unix ts>-<slug>, and open the pull request against demo-cloud-worker, never main.
```

Act 3 ends when the pull request against `demo-cloud-worker` carries Devin Review comments and CD has deployed the branch to `t-cw-<unix ts>-<slug>.demo.otterworks.app`. Open that link and show the tile and the column on the seeded users.

<a id="act-4-close"></a>
## Act 4: close

Go back to the `aws` persona session from act 1 and ask for the trail.

```text
Run make cw-trail and show me what the Devin roles did in this account today.
```

If the session is gone, run `make cw-trail` yourself on the operator machine. Act 4 ends when the table shows reads under `devin-cw-observer` and the redrive (`StartMessageMoveTask`) under `devin-cw-builder`, each with session name `devin-<session id>`. CloudTrail event history can trail the API call by several minutes, so run act 4 last.

<a id="timings"></a>
## Timings

The harness expectations come from `make cw-arm`, which prints them when it runs. Fill in the rehearsal column from your own rehearsal before you quote any number to an audience.

| Step | Harness expectation | Rehearsal |
|---|---|---|
| `make cw-arm` to first message in the DLQ | about 2 minutes | |
| `make cw-arm` to alarm `ALARM` | about 3 minutes | |
| Alarm `ALARM` to act 2 session started | | |
| Act 2 session started to after gate passed | | |
| Act 3 prompt to pull request opened | | |
| Branch push to `t-cw-<unix ts>-<slug>` reachable | | |
| Redrive to `StartMessageMoveTask` in `make cw-trail` | | |

<a id="cut-line"></a>
## Cut line

When the alarm has not reached `ALARM` 5 minutes after `make cw-arm`, run `make cw-status`.

- If the DLQ holds 1 message or more and the alarm is still `OK`, wait one more minute for the next 60 second evaluation.
- When the DLQ is still at 0, the consumer has not failed yet. Start act 3 now and come back to act 2 when the alarm fires.
- With the alarm at `ALARM` and no session started within 2 minutes, read `otterworks-cw-events-dlq` for a failed delivery. Start a session by hand in the same org with `!aws_cloud_worker` and paste the payload from `automation.md`, with `state` set to `ALARM`.

When act 2 has not passed its after gate by minute 20 of the demo, stop following the session on screen, show the cause Devin posted and the open pull request, and move to act 4.

<a id="reset"></a>
## Reset

Run the reset after every rehearsal and after the demo:

```bash
make cw-reset
make cw-status
```

`cw-reset` runs `cw-disarm` (restores the config from git and the notification-service image recorded at `arm`, so a fix image a session deployed does not carry into the next run; purges both queues, sets the alarm to `OK`, re-enables alarm actions), closes open pull requests whose branch starts with `demo-cw-`, deletes those branches, tears down the `cw-*` tenants, re-applies the retention drift for act 1 and ends any quiet window. When `cw-status` shows the live table equal to git, both queues at 0 and the alarm `OK`, the next run can start.

To stop a run in the middle without closing anything, run `make cw-disarm`. To keep the alarm from paging while you rehearse, run `make cw-quiet MINUTES=10`.

At the end of the cycle, run `make cw-teardown`. It runs the reset, removes the Devin roles from the cluster, deletes the reader's access keys and destroys the demo Terraform. Tenant `cloud-worker` stays unless you set `TEARDOWN_TENANT=true`, which also drops its hosts from external-dns and lets the Route53 records expire with the ingress. Delete the four `CW_*` org secrets afterward.
