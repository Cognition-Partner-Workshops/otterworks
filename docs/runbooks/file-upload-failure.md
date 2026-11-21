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

3. Confirm the bucket the service was configured with and that it exists:
   ```
   kubectl get deploy file-service -n otterworks -o jsonpath='{.spec.template.spec.containers[0].env}' | jq '.[] | select(.name=="S3_BUCKET")'
   aws s3api head-bucket --bucket <S3_BUCKET value>
   ```
   The expected value is the Terraform output `s3_file_bucket`
   (`terraform -chdir=infrastructure/terraform output -raw s3_file_bucket`), which
   `scripts/deploy-dev.sh` passes to Helm as `config.S3_BUCKET`.
4. Check for a recent config override on the release:
   ```
   helm history file-service -n otterworks
   helm get values file-service -n otterworks | grep S3_BUCKET
   ```

## Resolution Steps

- **Chaos flag set** (step 2 returns `1`): clear it with
  `scripts/inject-bug.sh <ID> reset` (or `redis-cli DEL chaos:file-service:upload_s3_error`).
  Uploads recover on the next request; no restart needed.
- **Wrong `S3_BUCKET` value** (step 3/4): redeploy with the Terraform output
  (`scripts/deploy-dev.sh`) or `helm rollback file-service <good revision> -n otterworks`,
  then `kubectl rollout restart deploy/file-service -n otterworks`.
- **Bucket genuinely missing**: `terraform -chdir=infrastructure/terraform apply` recreates
  `aws_s3_bucket.files`; existing object metadata in DynamoDB will point at keys that no
  longer exist, so treat this as data loss and follow the backup restore procedure.

file-service verifies the configured bucket with `HeadBucket` at startup and refuses to boot
if it is not accessible, so a bad `S3_BUCKET` now shows up as a failed rollout rather than
as a 5xx rate on live traffic.

## Post-Incident

- Confirm `FileUploadHighErrorRate` has resolved in Grafana and the file-service 5xx rate is
  back under 1%.
- Note in the incident record which path above applied and whether any uploads were lost
  (the request IDs of failed uploads are in the file-service logs).
