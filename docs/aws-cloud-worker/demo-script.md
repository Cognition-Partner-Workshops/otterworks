# AWS cloud worker: presenter script

You present from Partner Demo - ViewOnly, signed in as a Field Kit persona. The operator commands run on the machine that holds the `demo-cloud-worker` checkout and AWS admin credentials. Each act below has the step, what is on screen, and the line to say. Times are from the rehearsal on 2026-10-02 and the golden run in ViewOnly.

Everything in this file is already registered: playbook `playbook-5f0883504230448eb024a2b3307625bd`, automation `aws-cloud-worker-dlq-alarm` (`auto-653e19610ae1473196526847c15665f0`), the EventBridge rule that posts to it, and tenant `cloud-worker`.

## Tabs to open before the audience arrives

| Tab | URL | Signed in as |
|---|---|---|
| Devin, ViewOnly sessions | https://partner-workshops.devinenterprise.com/org/partner-demo-viewonly | persona (see below) |
| Devin, the automation | https://partner-workshops.devinenterprise.com/org/partner-demo-viewonly/automations/auto-653e19610ae1473196526847c15665f0 | persona |
| CloudWatch dashboard | https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=otterworks-cloud-worker | your AWS console login |
| Tenant | https://t-cloud-worker.otterworks.app | nobody |
| Repository, demo branch | https://github.com/Cognition-Partner-Workshops/otterworks/tree/demo-cloud-worker | your GitHub login |

## Signing in as the persona

1. Open https://fieldkit.devin.ai and sign in with your magic link.
2. Open https://partner-workshops.devinenterprise.com/auth/login?redirect=/&reauth=true and choose "Log in with SSO". The Field Kit page asks for an area and a persona.
3. Pick `Devin-Demo-Cloud` for the Cloud Engineer, or `Devin-Demo-AWS` for the AWS engineer. Both are Members of ViewOnly. The Product Manager is `Devin-Demo-Product`.
4. Land on the ViewOnly sessions list. If the page shows an org picker, choose Partner Demo - ViewOnly.

To switch persona during the demo, sign out of partner-workshops first and repeat from step 2. The Field Kit cookie stays, so the magic link is not needed twice.

| Persona | Field Kit group | Devin user |
|---|---|---|
| AWS engineer (act 1 and 4) | Devin-Demo-AWS | user-094334530455473bb8c587d207307833 |
| Cloud engineer (replies in act 2) | Devin-Demo-Cloud | user-3f836342a33f4c759f0edeb2805d6b58 |
| Product manager (act 3) | Devin-Demo-Product | user-f65e35477d3c403aaa0838632f20650b |

## Pre-flight, 30 minutes before

On the operator machine:

```bash
cd /home/ubuntu/repos/otterworks
export AWS_DEFAULT_REGION=us-east-1
git fetch origin && git checkout demo-cloud-worker && git pull
make cw-status
```

Expect: every pod `ready` except `admin-service` (its crash is a planted lab bug, leave it), `table live` equal to `table git`, queue and dlq at `0 visible`, alarm `OK, actions enabled`, `armed_at -`. Then confirm the image:

```bash
kubectl get deploy -n otterworks-cloud-worker notification-service -o jsonpath='{.spec.template.spec.containers[0].image}'
```

The printed tag should begin with `workshop-ep-contracts-2c2d7ff`, the golden image. If it names `demo-cw-...` instead, a run's fix image is still live and the alarm will not fire; run `make cw-apply` and check again. CD redeploys on every push to `demo-cloud-worker`, so do not push to the branch during the demo.

Check the automation tab shows `Active` and one past event at 100% success, and that the sessions list has no running session tagged `aws-cloud-worker`.

## Opening, 1 minute

Show: the tenant home page, then the CloudWatch dashboard with the DLQ at 0.

Say: "One team, one AWS account, and nobody has ten minutes. Watch Devin take the question, the page and the change."

## Act 1, ask, 4 minutes

Sign in as the AWS engineer, open a new session on repository `Cognition-Partner-Workshops/otterworks`, and paste:

```text
What runs in the demo tenant, how does a file share become a notification, and does the account match Terraform? Work from branch demo-cloud-worker and read .agents/skills/aws-cloud-worker/SKILL.md first.
```

Devin reads under the observer role and comes back with SNS `otterworks-cw-events` to SQS `otterworks-cw-notifications` to `notification-service` to DynamoDB `otterworks-cw-notifications`, the two IRSA roles, and the drift: the queue keeps messages for 14 days and Terraform says 4.

Say: "Devin read the account and the Terraform side by side, and found the drift before anyone ran a plan."

Leave this session open, because act 4 comes back to it, and start act 2 as soon as the session is working, so the alarm fires while Devin answers.

## Act 2, page, 14 minutes

On the operator machine, off camera:

```bash
make cw-arm
```

It points the consumer at a table that does not exist and publishes six `file_shared` events. Then the clock runs on its own:

| Minute from `cw-arm` | What happens | Show |
|---|---|---|
| 0 to 2 | consumer fails each message three times, SQS moves them to the DLQ | dashboard, DLQ depth climbing to 6 |
| about 3:45 | alarm `OK` to `ALARM`, EventBridge posts to the automation | alarm history; the automation tab's Events count goes up |
| plus 1 second | a session nobody typed appears, owner `automation-service`, tagged `aws-cloud-worker` | sessions list, open it |
| 2 to 3 | Devin posts the cause: live table `otterworks-cw-notifications-v2`, git says `otterworks-cw-notifications`, changed by hand in Helm | session transcript |
| 3 to 8 | `make cw-apply` under the builder role, DLQ redrive of 6, `make cw-verify EXPECT=after` 5/5, PR against `demo-cloud-worker` | session; the PR link |

While the DLQ is climbing, say: "Somebody changed a setting by hand last week. Nobody knows yet."

When the session appears, say: "Nobody started that. CloudWatch paged a Devin Automation the same way it would page a person."

When the cause is posted, say: "Devin found it in the telemetry before anyone filed a ticket."

When Devin has posted the restore, the redrive and the gate result, and the session is waiting, switch to the Cloud Engineer persona (or stay as the AWS engineer; either is a Member) and reply:

```text
Thanks, that matches what I saw in the Helm history. Keep the PR against demo-cloud-worker and leave cloudworker/ and eventing.env alone. Finish with the CloudTrail close (make cw-trail) so we have the record of what the observer read and what the builder changed, then post the summary and sign off.
```

Say: "Devin put git back in charge, replayed the lost notifications and proved it with a gate it cannot edit. The pull request makes sure a bad table name fails at boot next time."

Independent check, from the operator machine, any time after Devin says the gate passed:

```bash
make cw-verify EXPECT=after
```

The gate should print `PASS (5/5)`, and that number is yours to quote; the session's own gate output is its claim.

## Act 3, change, 6 minutes, optional

Sign in as the Product Manager, open a new session on the same repository, and paste:

```text
I'm the product manager for the OtterWorks admin dashboard in Cognition-Partner-Workshops/otterworks. On the dashboard overview, add a "Signed in today" tile with the number of users who signed in today, and add a "Last sign-in" column to the users table. Update the admin API docs for any admin endpoint you add or change. Deploy it somewhere I can open in a browser and send me the link. Work from the demo-cloud-worker branch, push to a new branch named demo-cw-<unix ts>-<slug>, and open the pull request against demo-cloud-worker, never main.
```

Act 3 ends when the PR carries Devin Review comments and CD has deployed the branch to `t-cw-<unix ts>-<slug>.demo.otterworks.app`. Open the link.

Say: "The person who knew what was needed asked for it directly, and the review and the deploy ran the way they run for your engineers."

Start act 3 right after the act 2 reply so its deploy finishes while you close.

## Act 4, close, 2 minutes

Back in the act 2 session, Devin's last message is the CloudTrail table. Reads are under `devin-cw-observer`, the redrive (`StartMessageMoveTask`) under `devin-cw-builder`, each with session name `devin-<session id>`. If the session has not posted it, run on the operator machine:

```bash
make cw-trail
```

CloudTrail can lag the call by several minutes, so this goes last.

Say: "Every call Devin made is in CloudTrail under a role you scoped and a session you can open."

## If something slips

- Alarm not in `ALARM` five minutes after `cw-arm`: `make cw-status`. DLQ above 0 and alarm `OK` means wait one more evaluation. DLQ at 0 means the consumer did not fail; check the image as in pre-flight, run `make cw-apply`, then `make cw-arm` again.
- Alarm in `ALARM` and no session after two minutes: open the automation tab's Events list. If the delivery failed, start a session by hand in ViewOnly with `!aws_cloud_worker` and the payload from `docs/aws-cloud-worker/automation.md` with `state` set to `ALARM`.
- Session stuck past minute 20: show the cause it posted and the open PR, then move to act 4.
- Devin asks a question you did not expect: answer as the Cloud Engineer in one line. It has the skill; it does not need commands from you.

## After the demo

```bash
make cw-reset
make cw-status
```

`cw-reset` restores the config and the baseline image, purges both queues, sets the alarm to `OK`, closes the `demo-cw-*` PRs and branches, drops the act 3 tenant and re-plants the retention drift. The status should read the same as pre-flight. Do not merge the fix PR; the baseline PR https://github.com/Cognition-Partner-Workshops/otterworks/pull/1793 is the one that merges into `main`.

## Rules for the run

- Never merge a `demo-cw-*` PR, and never open a PR against `main` during the demo.
- Leave `admin-service` alone; its crash loop belongs to another lab.
- Do not push to `demo-cloud-worker` while a run is live; CD would restart the consumer mid-session.
- The reader key and the builder role can change the tenant. Rotate them with `make cw-credentials` at the end of the cycle, or `make cw-teardown` when the demo retires.
