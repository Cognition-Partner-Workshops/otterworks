# Runbook: File Upload Failures

**Severity:** High

## Alert

`FileUploadHighErrorRate` -- fires when file-service 5xx rate exceeds 10% over a 1-minute window.

## Symptoms

- Users cannot upload files; the UI shows generic upload error messages.
- The Chaos Scenarios dashboard shows elevated error rates on the file-service panel.
- Application logs contain `NoSuchBucket` errors from the AWS S3 SDK.

## Investigation Steps

1. Confirm the error in file-service logs. Since the fix for this incident the
   storage error log line carries the bucket and the SDK error code:
   ```
   kubectl logs -l app=file-service --tail=100 -n otterworks | grep -i "S3 put_object failed\|NoSuchBucket"
   ```
   `error_code=NoSuchBucket bucket=<name>` tells you exactly which bucket the
   service tried to write to.
2. Compare that bucket with what the service was deployed with and what
   Terraform created:
   ```
   kubectl -n otterworks get configmap file-service-config -o jsonpath='{.data.S3_BUCKET}'
   terraform -chdir=infrastructure/terraform output -raw s3_file_bucket
   ```
   `scripts/deploy-dev.sh` wires `config.S3_BUCKET` from the Terraform output,
   so the two should match. A mismatch means a config override (for example the
   `file-bad-bucket` scenario in `scripts/bug-catalog.yaml`, or a manual
   `helm upgrade --set`) or a bucket rename/deletion in Terraform.
3. Check the chaos flag `chaos:file-service:upload_s3_error` in the tenant's
   Redis. Before the fix, `upload_file` swapped the configured bucket for a
   hardcoded nonexistent one whenever this key existed, so a set flag was the
   usual cause even though every config knob looked correct:
   ```
   redis-cli EXISTS chaos:file-service:upload_s3_error
   ```

## Resolution Steps

- **Bucket in the log matches `S3_BUCKET` but does not exist:** the bucket was
  renamed or destroyed. Recreate it via Terraform (`modules/storage`) or point
  `S3_BUCKET` at the bucket that does exist and roll out file-service.
- **Bucket in the log differs from `S3_BUCKET`:** the running image still has
  the chaos redirect. Deploy a build that includes the fix (uploads always use
  the configured `S3Client`) and clear the flag:
  ```
  scripts/inject-bug.sh <tenant> reset
  ```
- **Config override:** `helm upgrade` the release with the correct
  `config.S3_BUCKET` (or redeploy with `scripts/deploy-dev.sh`, which sets it
  from Terraform) and restart the rollout.

Verify: `FileUploadHighErrorRate` resolves within two evaluation windows once
uploads return `201` again; a single `POST /api/v1/files/upload` through the
gateway should succeed.

## Post-Incident

- Confirm no other handler reads a Redis chaos flag that can change which AWS
  resource a request targets; runtime behaviour toggles must never substitute
  infrastructure names.
- If the bucket was genuinely misnamed, add the bucket name to the
  file-service startup log so a misconfiguration is visible at boot rather than
  on the first upload.
