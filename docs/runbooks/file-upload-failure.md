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
   `S3 PutObject failed` log line carries the bucket the service actually wrote
   to and the SDK error code:
   ```
   kubectl logs -l app=file-service --tail=100 -n otterworks | grep -i "PutObject failed\|NoSuchBucket\|HeadBucket"
   ```
2. Compare the `bucket` field in that log line with the configured value:
   ```
   kubectl -n otterworks get configmap file-service-config -o jsonpath='{.data.S3_BUCKET}'
   aws s3api head-bucket --bucket <that value>
   ```
   - Same bucket, `NoSuchBucket`/`NotFound`: `S3_BUCKET` is wrong (check the
     last `helm upgrade` of `file-service` and the Terraform `s3_file_bucket`
     output).
   - Different bucket: the code is not using the configured bucket (this was
     the root cause of the first occurrence; see below).
3. Check the pod started cleanly. file-service now runs `HeadBucket` against
   `S3_BUCKET` at boot and exits with `File Service refusing to start` if the
   bucket is missing, so a wrong value shows up as a crash-looping rollout
   rather than as upload 500s.

## Resolution Steps

- Wrong `S3_BUCKET` value: redeploy with the correct value
  (`scripts/deploy-tenant.sh <ID>` re-reads it from Terraform). The new pods
  only become ready once `HeadBucket` succeeds.
- Bucket genuinely missing: restore it with Terraform (`module.storage`) before
  rolling the service; do not create it by hand.

## Post-Incident

First occurrence (alert `FileUploadHighErrorRate`): `S3_BUCKET` was correct.
`handlers::upload_file` replaced the configured bucket with a hard-coded
nonexistent one whenever the Redis key `chaos:file-service:upload_s3_error`
existed, so only uploads failed while downloads, deletes and copies (which used
the configured bucket) kept working. The fix removed that code path (uploads
always go through the shared `S3Client`), added the startup `HeadBucket` check,
and made the upload error log name the bucket and the S3 error code. The
`file-upload-fails` entry in `scripts/bug-catalog.yaml` and the admin chaos
control for `file-service → upload_s3_error` no longer affect file-service.
