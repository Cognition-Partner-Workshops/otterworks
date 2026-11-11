# Runbook: File Upload Failures

**Severity:** High

## Alert

`FileUploadHighErrorRate` -- fires when file-service 5xx rate exceeds 10% over a 1-minute window.

## Symptoms

- Users cannot upload files; the UI shows generic upload error messages.
- The Chaos Scenarios dashboard shows elevated error rates on the file-service panel.
- Application logs contain `NoSuchBucket` errors from the AWS S3 SDK.
- `POST /api/v1/files/upload` returns `500 {"error":"storage_error","message":"S3 error: upload failed (bucket \"<name>\"): ... NoSuchBucket ..."}`.
  The bucket name in the message is the one the service actually used.

## How the bucket name is resolved

file-service reads `S3_BUCKET` at startup (`services/file-service/src/config.rs`). The
code default is `otterworks-files`, which only exists in LocalStack (Docker Compose).
On EKS the real bucket is created by Terraform as `<project>-files-<environment>`
(`otterworks-files-dev`) and `scripts/deploy-dev.sh` / `scripts/deploy-tenant.sh` pass it
through Helm as `config.S3_BUCKET` from the Terraform output `s3_file_bucket`. The deploy
scripts refuse to deploy file-service when that output is empty, and the service refuses to
start when `S3_BUCKET` is set but empty. On startup it runs `HeadBucket` and logs
`S3 bucket reachable` or `Configured S3 bucket is not reachable`.

There are three known ways to end up writing to a bucket that does not exist:

| Cause | Where to look | Bucket name in the error |
|---|---|---|
| Chaos flag `chaos:file-service:upload_s3_error` (scenario `file-upload-fails`) | the tenant's Redis | `otterworks-files-chaos-nonexistent` |
| Config override (scenario `file-bad-bucket`, or a manual `helm upgrade --set config.S3_BUCKET=...`) | the `file-service-config` ConfigMap | whatever the override set (`otterworks-does-not-exist` for the scenario) |
| Genuine misconfiguration: deploy ran without Terraform outputs, bucket renamed/removed, or the chart default fell through | ConfigMap vs `terraform output s3_file_bucket` vs `aws s3 ls` | `otterworks-files` or an empty string |

## Investigation Steps

1. Confirm the error and read the bucket name out of the file-service logs
   (`NS=otterworks` for the golden app, `otterworks-<ID>` for a tenant):
   ```
   kubectl logs -l app.kubernetes.io/name=file-service --tail=200 -n "$NS" | grep -i "NoSuchBucket\|bucket"
   ```
   Also check what the pod reported at startup:
   ```
   kubectl logs -l app.kubernetes.io/name=file-service -n "$NS" | grep -i "S3 bucket"
   ```
2. Check whether the chaos flag is set in the tenant's own Redis:
   ```
   kubectl exec -n "$NS" deploy/redis -- redis-cli EXISTS chaos:file-service:upload_s3_error
   ```
   `1` means the alert is a chaos injection (`scripts/inject-bug.sh <ID> file-upload-fails`),
   not an infrastructure fault; the upload handler swaps in the chaos bucket per request.
3. Compare the configured bucket with the one Terraform owns:
   ```
   kubectl get configmap file-service-config -n "$NS" -o jsonpath='{.data.S3_BUCKET}'; echo
   terraform -chdir=infrastructure/terraform output -raw s3_file_bucket; echo
   aws s3api head-bucket --bucket "$(kubectl get configmap file-service-config -n "$NS" -o jsonpath='{.data.S3_BUCKET}')"
   ```
   Any mismatch, an empty value, or a `404` from `head-bucket` is the root cause.
4. Check for a recent change to the release or the bucket:
   ```
   helm history file-service -n "$NS"
   git log --oneline -10 -- scripts/deploy-dev.sh scripts/lib/tenant-common.sh infrastructure/terraform/modules/storage
   aws cloudtrail lookup-events --lookup-attributes AttributeKey=ResourceName,AttributeValue=<bucket> --max-results 20
   ```
5. Rule out credentials: a `403` from `head-bucket` run with the pod's IRSA role (not your
   own credentials) means the role, not the bucket name, is wrong.

## Resolution Steps

- **Chaos flag set:** clear it. This is instant and needs no restart.
  ```
  scripts/inject-bug.sh <ID> reset        # or: redis-cli DEL chaos:file-service:upload_s3_error
  ```
- **Wrong or empty `S3_BUCKET` in the ConfigMap:** redeploy the service from the source of
  truth rather than editing the ConfigMap by hand:
  ```
  scripts/deploy-dev.sh --skip-terraform --skip-build    # golden app (redeploys every release)
  scripts/deploy-tenant.sh <ID>                          # a tenant
  ```
  If you must hot-fix, `helm upgrade file-service infrastructure/helm/file-service -n "$NS"
  --reuse-values --set-string config.S3_BUCKET=<bucket>` then
  `kubectl rollout restart deploy/file-service -n "$NS"`.
- **Bucket really is gone:** restore it with Terraform (`terraform -chdir=infrastructure/terraform
  apply -target=module.storage`) and redeploy. Do not create it by hand; the name, tags and
  policies come from `infrastructure/terraform/modules/storage`.
- Verify: the new pod logs `S3 bucket reachable`, a test upload through the gateway returns
  `201`, and the `FileUploadHighErrorRate` alert resolves within two evaluation windows.

## Post-Incident

- Record which of the three causes it was. If it was a chaos or config scenario left armed
  on a tenant, note who armed it and reset the tenant.
- If it was a genuine misconfiguration, add how the bad value got past the deploy guard
  (`scripts/deploy-dev.sh`, `scripts/lib/tenant-common.sh`) and close that path.
- Never fix a page by widening the alert threshold or by changing the rule.
