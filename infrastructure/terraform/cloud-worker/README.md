# Cloud worker infrastructure

This Terraform root builds the AWS side of the `aws-cloud-worker` demo. It shares the cluster `otterworks-dev` and the state bucket with the main stack. Its state key is `otterworks/cloud-worker/terraform.tfstate`.

## Resources

- SNS topic `otterworks-cw-events`, subscribed to the queue `otterworks-cw-notifications`.
- SQS queue `otterworks-cw-notifications`. After three receives a message moves to `otterworks-cw-notifications-dlq`.
- DynamoDB table `otterworks-cw-notifications`, with the same keys and index as the main notifications table.
- DynamoDB table `otterworks-cw-notification-preferences`, keyed on `userId`. The consumer reads it before it writes each notification.
- IRSA roles `otterworks-cw-notification-service` and `otterworks-cw-file-service`. Each trusts one service account in `otterworks-cloud-worker`.
- IAM user `devin-cw-reader`. It may assume `devin-cw-observer` for reads and `devin-cw-builder` for the restore and the redrive.
- Alarm `otterworks-cw-notifications-dlq-depth`. It fires when the DLQ holds one message.
- Dashboard `otterworks-cloud-worker`.
- EventBridge rule `otterworks-cw-dlq-alarm-to-devin`. It posts each ALARM transition to the Devin webhook. Failed posts go to `otterworks-cw-events-dlq`.

Every resource carries the tag `demo=aws-cloud-worker`.

## Usage

`make cw-up` at the repository root applies this root with the webhook URL and secret from `~/.cw-webhook.json`.

To preview the change by hand:

```bash
cd infrastructure/terraform/cloud-worker
terraform init
terraform plan
```

The file-service role reads the bucket and table names from the main stack's state. Apply the main stack first.

`make cw-credentials` issues the access key for `devin-cw-reader`, since Terraform creates none.

The harness owns the alarm's actions switch, so Terraform ignores changes to it.
