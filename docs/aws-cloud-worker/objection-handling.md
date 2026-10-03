# Objection handling

Short answers to the pushback heard most often on this demo. Each answer points at something the audience saw.

## Why would we give an AI write access to our AWS account?

Devin read the account through `devin-cw-observer`, which is AWS managed `ReadOnlyAccess`. It assumed `devin-cw-builder` only for the restore and the redrive. The builder role adds the SQS redrive and purge actions on two queues and `SetAlarmState` on one alarm, and Kubernetes `edit` in one namespace. Act 4 showed both roles in CloudTrail with the session name on every call.

## What happens when Devin is wrong?

The after gate is a script in the repository that the operator owns. It checks the live table against git, the DLQ depth, the alarm state, pod readiness and one fresh event in DynamoDB. The skill forbids edits to the gate during a run, and the fix arrives as a pull request a person reviews.

## A runbook script could restore the config

The restore is the script `make cw-apply`, and Devin decided to run the script after reading the alarm, the queues, the logs and the Helm history, and it wrote the startup check that makes the next bad table name fail at boot. Your team already has scripts. The gap is a person at a keyboard who reads the telemetry at 2 a.m.

## Our production runs in two accounts, so does this apply?

The record asked for a production-like account and a development account. This build uses one tenant and two roles, so CloudTrail separates the reads from the writes by role. With two accounts, the observer role lives in production and the builder role lives in development, and the playbook stays the same.

## We use Slack and PagerDuty, and the demo uses neither

The page reached Devin as a webhook from EventBridge. Any tool that can post a webhook can start the same Automation, and Devin can also start from a Slack message. The demo leaves Slack out to keep the path to one AWS service and one Devin feature.

## Who pays when an alarm flaps?

The Automation caps each session at 30 ACU, starts at most 3 sessions per hour, and runs one at a time with no queue. A second page during a run is dropped.

## Should a product manager be shipping code?

In act 3 the product manager asked in plain language. Devin opened a pull request against `demo-cloud-worker`, Devin Review commented on it, and CD deployed the branch to its own tenant. Nothing merged. An engineer still decides what reaches the main branch.
