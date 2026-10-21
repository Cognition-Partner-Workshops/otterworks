# Runbook: File Upload Failures

**Severity:** High

## Alert

`FileUploadHighErrorRate` -- fires when file-service 5xx rate exceeds 10% over a 1-minute window.

## Symptoms

- Users cannot upload files; the UI shows generic upload error messages.
- The Chaos Scenarios dashboard shows elevated error rates on the file-service panel.
- Application logs contain `NoSuchBucket` errors from the AWS S3 SDK.

## Investigation Steps

1. Confirm the error in file-service logs. A failed upload logs `S3 upload failed`
   with the `bucket` it tried to write to:
   ```
   kubectl logs -l app=file-service --tail=100 -n otterworks | grep -i "NoSuchBucket\|S3 upload failed"
   ```
2. Compare the bucket in the log line with the bucket the service is configured for:
   ```
   kubectl get cm file-service-config -n otterworks -o jsonpath='{.data.S3_BUCKET}'
   terraform -chdir=infrastructure/terraform output -raw s3_file_bucket
   ```
   `S3_BUCKET` is wired from the `s3_file_bucket` Terraform output by
   `scripts/deploy-dev.sh` / `scripts/lib/tenant-common.sh`. The two should match.
3. Check for a recent config override or Helm release that changed `config.S3_BUCKET`
   (e.g. the `file-bad-bucket` scenario in `scripts/bug-catalog.yaml`):
   ```
   helm history file-service -n otterworks
   helm get values file-service -n otterworks | grep S3_BUCKET
   ```
4. Confirm the bucket exists and the service role can reach it:
   ```
   aws s3api head-bucket --bucket "$(kubectl get cm file-service-config -n otterworks -o jsonpath='{.data.S3_BUCKET}')"
   ```

## Resolution Steps

- **Misconfigured `S3_BUCKET`**: redeploy file-service with the correct value (re-run
  `scripts/deploy-dev.sh` / `scripts/deploy-tenant.sh <ID>`, or `helm upgrade` with the
  Terraform `s3_file_bucket` output). Since the fix for `FileUploadHighErrorRate`, file-service
  runs `HeadBucket` on startup and refuses to start when the bucket is unreachable, so a bad
  value fails the rollout (`CrashLoopBackOff`, `File Service refusing to start` in logs)
  instead of returning 500s on uploads. Check the rollout after redeploying:
  ```
  kubectl rollout status deploy/file-service -n otterworks
  ```
- **Code redirecting uploads away from the configured bucket**: the upload handler must
  write to `S3Client.bucket` only. The handler no longer consults any runtime flag to pick
  a bucket; if a 500 names a bucket other than the configured one, treat it as a regression.
- The alert resolves on its own once the upload 5xx rate drops below 10% for the
  evaluation window. Verify with an upload through the gateway:
  ```
  curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $TOKEN" \
    -F file=@README.md http://localhost:8080/api/v1/files/upload
  ```

## Post-Incident

- Record which bucket the service was writing to, which bucket it was configured for, and
  the change (deploy, Helm override, code) that introduced the difference.
- If the cause was a config change, add a check to the deploy path that compares
  `config.S3_BUCKET` with the Terraform output before `helm upgrade`.
- Uploads that failed were never persisted (the S3 write happens before the metadata
  write), so there is no orphaned metadata to clean up; users need to retry.
