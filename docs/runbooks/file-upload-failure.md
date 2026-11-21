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
   The `bucket=` field on the `Uploaded object to S3` / `upload failed` log lines is the
   bucket the service actually wrote to. Compare it with step 2.
2. Check the configured bucket. file-service reads `S3_BUCKET` once at startup
   (`services/file-service/src/config.rs`) and logs `S3 bucket reachable` or
   `Configured S3_BUCKET is not reachable` in its first lines:
   ```
   kubectl -n otterworks get configmap file-service-config -o jsonpath='{.data.S3_BUCKET}'
   kubectl logs -l app=file-service -n otterworks | grep -i "S3_BUCKET\|bucket reachable"
   aws s3api head-bucket --bucket "$(kubectl -n otterworks get configmap file-service-config -o jsonpath='{.data.S3_BUCKET}')"
   ```
   On the dev cluster the correct value is Terraform's `s3_file_bucket` output
   (`terraform -chdir=infrastructure/terraform output -raw s3_file_bucket`); locally it is
   `otterworks-files` (`docker-compose.yml`).
3. Check for a recent config change on the release:
   ```
   helm -n otterworks history file-service
   helm -n otterworks get values file-service | grep S3_BUCKET
   ```
   The `file-bad-bucket` demo scenario (`scripts/bug-catalog.yaml`) injects exactly this
   misconfiguration via `--set-string config.S3_BUCKET=otterworks-does-not-exist`.
4. If the configured bucket is correct and reachable but uploads still fail with
   `NoSuchBucket`, the running image overrides the bucket at request time. Before
   this runbook was completed, `upload_file` in `services/file-service/src/handlers.rs`
   swapped the configured bucket for the hard-coded `otterworks-files-chaos-nonexistent`
   whenever the Redis key `chaos:file-service:upload_s3_error` existed:
   ```
   redis-cli EXISTS chaos:file-service:upload_s3_error
   ```
   That override has been removed; uploads now always use `S3_BUCKET`. If you see it in
   the logs (`Chaos flag active: redirecting upload to nonexistent bucket`), the tenant
   is running a pre-fix image.

## Resolution Steps

- **Wrong `S3_BUCKET` value:** redeploy the release with the correct value. For a tenant,
  `scripts/deploy-tenant.sh <ID>` re-wires config from Terraform outputs; for dev,
  `scripts/deploy-dev.sh`. Confirm with the startup log line `S3 bucket reachable`.
- **Bucket genuinely missing:** `terraform -chdir=infrastructure/terraform apply` recreates
  `module.storage`; never create the bucket by hand.
- **Pre-fix image with the chaos override:** clear the flag as an immediate mitigation
  (`redis-cli DEL chaos:file-service:upload_s3_error`, or
  `scripts/inject-bug.sh <ID> reset` for a tenant), then roll the release to an image
  that no longer carries the override.
- Verify: `FileUploadHighErrorRate` resolves within two evaluation windows and an upload
  through the web app returns `201`.

## Post-Incident

- Record which of the three causes above applied and link the Helm revision / commit.
- If the cause was configuration, add the bucket name to the deploy's post-apply smoke
  check so a bad value is caught before traffic reaches it.
- Any fault injection used for demos must stay in `scripts/bug-catalog.yaml` /
  `scripts/inject-bug.sh` (tenant-scoped, outside the service), not in the service's
  request path.
