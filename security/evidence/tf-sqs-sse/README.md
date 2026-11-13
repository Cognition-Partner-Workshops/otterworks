# Checkov evidence: SQS server-side encryption (application Terraform)

- Scanner: Checkov 3.4.5 (`checkov --version`), framework `terraform`, no skips, no `.checkov.yaml`, no inline suppressions.
- Baseline: `origin/demo-ciso` @ `449e5f7ae`. After: this branch.
- Root: `infrastructure/terraform` (the root `scripts/spinup-dev.sh` and `scripts/deploy-dev.sh` init/apply; S3 backend `otterworks-terraform-state`, key `otterworks/terraform.tfstate`). `module.messaging` is created unconditionally (no `count`).

| Scope | Baseline passed/failed | After passed/failed | Resources |
|---|---|---|---|
| Full `infrastructure/terraform` (incl. azure, legacy-portal-*, demo-aws, cloud-worker) | 565 / 170 | 569 / 166 | 213 / 213 |
| Targeted `infrastructure/terraform/modules/messaging` | 17 / 5 | 21 / 1 | 11 / 11 |

Cleared (CKV_AWS_27 "Ensure all data stored in the SQS queue is encrypted", 4 findings):
`module.messaging.aws_sqs_queue.{notifications,notifications_dlq,analytics_events,search_indexing}`.
No new failures appear in the full-directory diff.

Residual in this module: CKV_AWS_26 `aws_sns_topic.events` (SNS topic not KMS-encrypted). Not changed here:
AWS documents that publishers to an SSE topic need `kms:GenerateDataKey*`/`kms:Decrypt` on the topic key, and
an encrypted topic delivering to SQS needs a customer-managed key with a policy for the SNS service principal.
That needs a key, key policy and IRSA changes for api-gateway/document-service/collab-service, so it is a design change, not a one-line fix.

## Files

- `checkov-full-{baseline,after}.txt` — raw `checkov -d infrastructure/terraform --framework terraform --quiet --compact -o cli`
- `checkov-module-messaging-{baseline,after}.json` — raw `checkov -d infrastructure/terraform/modules/messaging --framework terraform -o json` (minified with `jq -c`)

## Reproduce

```bash
pip install checkov==3.4.5
git worktree add /tmp/base 449e5f7ae
for r in /tmp/base .; do
  (cd "$r" && checkov -d infrastructure/terraform --framework terraform --quiet --compact -o cli | grep -E '^Passed')
  (cd "$r" && checkov -d infrastructure/terraform/modules/messaging --framework terraform --quiet --compact -o cli | grep -E '^Passed|FAILED')
done
cd infrastructure/terraform && terraform fmt -check -recursive && terraform init -backend=false && terraform validate
```

Static scan of source only. It says nothing about the live queues' current attributes (see the PR for read-only checks).
