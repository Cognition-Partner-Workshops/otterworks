# Checkov evidence: audit archive bucket versioning (application Terraform)

- Scanner: Checkov 3.4.5 (`checkov --version`), framework `terraform`, no skips, no `.checkov.yaml`, no inline suppressions.
- Baseline: `origin/demo-ciso` @ `449e5f7ae`. After: this branch.
- Root: `infrastructure/terraform` (the root `scripts/spinup-dev.sh` and `scripts/deploy-dev.sh` init/apply; S3 backend `otterworks-terraform-state`, key `otterworks/terraform.tfstate`). `module.storage` is created unconditionally.

| Scope | Baseline passed/failed | After passed/failed | Resources |
|---|---|---|---|
| Full `infrastructure/terraform` (incl. azure, legacy-portal-*, demo-aws, cloud-worker) | 565 / 170 | 568 / 168 | 213 / 215 |
| Targeted `infrastructure/terraform/modules/storage` | 32 / 14 | 35 / 12 | 11 / 13 |

Cleared on `module.storage.aws_s3_bucket.audit_archive`:
- CKV_AWS_21 "Ensure all data stored in the S3 bucket have versioning enabled"
- CKV2_AWS_61 "Ensure that an S3 bucket has a lifecycle configuration"

The two new resources (`aws_s3_bucket_versioning.audit_archive`, `aws_s3_bucket_lifecycle_configuration.audit_archive`) add passing checks (incl. CKV_AWS_300 abort-incomplete-multipart) and no new failures appear in the full-directory diff.

Residual on the audit bucket (advisory, not changed): CKV_AWS_18 access logging, CKV_AWS_144 cross-region replication, CKV2_AWS_62 event notifications.

## Files

- `checkov-full-{baseline,after}.txt` — raw `checkov -d infrastructure/terraform --framework terraform --quiet --compact -o cli`
- `checkov-module-storage-{baseline,after}.json` — raw `checkov -d infrastructure/terraform/modules/storage --framework terraform -o json` (minified with `jq -c`)

## Reproduce

```bash
pip install checkov==3.4.5
git worktree add /tmp/base 449e5f7ae
for r in /tmp/base .; do
  (cd "$r" && checkov -d infrastructure/terraform --framework terraform --quiet --compact -o cli | grep -E '^Passed')
  (cd "$r" && checkov -d infrastructure/terraform/modules/storage --framework terraform --quiet --compact -o cli | grep -E '^Passed|FAILED')
done
cd infrastructure/terraform && terraform fmt -check -recursive && terraform init -backend=false && terraform validate
```

Static scan of source only. It says nothing about the live bucket's current versioning state (see the PR for read-only checks).
