# Runbook: File Upload Failures

**Severity:** High

## Alert

`FileUploadHighErrorRate` -- fires when file-service 5xx rate exceeds 10% over a 1-minute window.

## Symptoms

- Users cannot upload files; the UI shows generic upload error messages.
- The Chaos Scenarios dashboard shows elevated error rates on the file-service panel.
- Application logs contain `NoSuchBucket` errors from the AWS S3 SDK.

## Investigation Steps

1. Confirm the error in file-service logs:
   ```
   kubectl logs -l app=file-service --tail=100 -n otterworks | grep -i "NoSuchBucket\|S3\|500"
   ```
2. Check whether the chaos flag `chaos:file-service:upload_s3_error` is set in Redis:
   ```
   redis-cli EXISTS chaos:file-service:upload_s3_error
   ```

3. Check the bucket the pod is actually configured with against the bucket
   that exists in the account:
   ```
   kubectl get configmap file-service-config -n otterworks -o jsonpath='{.data.S3_BUCKET}'
   aws s3api head-bucket --bucket "$(kubectl get configmap file-service-config -n otterworks -o jsonpath='{.data.S3_BUCKET}')"
   helm history file-service -n otterworks   # a recent revision with a changed S3_BUCKET is the smoking gun
   ```
4. Since the fix in this runbook's PR, file-service calls `HeadBucket` on
   `S3_BUCKET` at startup and refuses to start if the bucket is missing, so a
   bad `S3_BUCKET` shows up as a crash-looping pod with
   `S3 bucket verification failed` in its logs instead of a 5xx spike.

## Resolution Steps

- **Chaos flag set** (`EXISTS` returned `1`): clear it and confirm uploads
  recover. The flag auto-expires, but do not wait for it:
  ```
  redis-cli DEL chaos:file-service:upload_s3_error
  ```
- **`S3_BUCKET` points at a bucket that does not exist**: roll the release back
  to the last revision whose `S3_BUCKET` is the real bucket (the Terraform
  `s3_file_bucket` output), or redeploy from the source of truth:
  ```
  helm rollback file-service <good-revision> -n otterworks
  # or
  scripts/deploy-dev.sh   # / scripts/deploy-tenant.sh <ID> for a tenant
  ```
  Never hand-edit the ConfigMap; the next deploy would overwrite it.
- Verify: `FileUploadHighErrorRate` resolves within two evaluation windows and
  a test upload through the gateway returns `201`:
  ```
  curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $TOKEN" \
    -F file=@README.md http://localhost:8080/api/v1/files/upload
  ```

## Post-Incident

- The upload handler used to swap the configured bucket for a nonexistent one
  when the Redis chaos flag was present; that code path was removed so the
  service only ever writes to `S3_BUCKET`, and startup now fails fast on a
  missing bucket (`S3Client::verify_bucket`).
- If the trigger was a config change, record which deploy introduced it and
  add a `head-bucket` check to the deploy script's preflight so a bad value
  is caught before `helm upgrade`.
