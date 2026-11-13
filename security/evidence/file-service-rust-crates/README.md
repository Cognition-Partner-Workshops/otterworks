# file-service: Rust crate CVEs (Trivy, Cargo.lock)

## Exposure, in plain words
The crates below were compiled into the `file-service` binary, which handles uploads and downloads and talks to S3, DynamoDB and SNS:
- actix-http 3.12.0, GHSA-xhj4-vrgc-hr34 (MEDIUM): HTTP/1.1 CL.TE request smuggling. A crafted request can slip a second request
  past an upstream proxy.
- aws-smithy-json 0.62.5, CVE-2026-18140 (HIGH): deeply nested JSON in an AWS response causes unbounded recursion, so the
  process can crash.
- rustls-webpki 0.101.7, GHSA-82j2-j2ch-gfr8 (HIGH), plus 2 LOW; and rustls 0.21.12 / 0.23.38 (3 MEDIUM, 6 LOW): flaws in
  certificate validation and TLS handling on outbound AWS connections. The 0.21/0.101 copies came from the AWS SDK's legacy
  hyper-0.14 TLS client.
- opentelemetry_sdk 0.21.2, CVE-2026-48504 (MEDIUM): unbounded memory allocation from W3C baggage headers.
- protobuf 2.28.0 (pulled in by prometheus 0.13), CVE-2025-53605 (MEDIUM): uncontrolled recursion while parsing.

## Fix
Only `services/file-service/Cargo.toml` and `Cargo.lock` change; there are no source edits.
- Lockfile bumps: actix-http 3.12.1, aws-smithy-json 0.62.7 (with aws-smithy-runtime-api 1.12.3 and aws-smithy-types 1.9.0),
  rustls 0.23.46, rustls-webpki 0.103.17.
- `aws-sdk-s3/-dynamodb/-sns`: same version ranges, now with `default-features = false` and the features
  `default-https-client` + `rt-tokio` (S3 also keeps `http-1x` and `sigv4a`). This drops the legacy `rustls 0.21` client.
  aws-config and the AWS SDK versions are unchanged. aws-config defaults stay on, so the credential chain is unchanged
  (env, web identity/IRSA, SSO, process).
- OpenTelemetry crates moved together to 0.32 (tracing-opentelemetry 0.33), and prometheus to 0.14 (which uses protobuf 3.7.2).

## Results (Trivy 0.71.0, same DB, `--scanners vuln --ignorefile /dev/null`, all severities)
| | Cargo.lock records | HIGH | MEDIUM | LOW | image total | image ID |
|---|---|---|---|---|---|---|
| before | 14 | 2 | 6 | 6 | 422 | `sha256:acf09107eeab…` |
| after | **0** | 0 | 0 | 0 | 422 | `sha256:80c4ff4c76f2…` |

The image count stays at 422. The release binary carries no `cargo auditable` metadata, so `trivy image` cannot see
compiled-in crates at all, and the 422 records are all Debian 13.7 OS packages. The crate fix is therefore proven by
`trivy fs` on the lockfile the binary is built from. Of the 422 OS records, 3 are fixable (zlib1g, handled in a separate PR)
and the rest have no Debian fix. No ignore file or skips were used.

## Behaviour checks
- `cargo test`: 11/11 passed before and after.
- `cargo fmt --check` and `cargo clippy -- -D warnings`: clean (mirrors ci.yml).
- `cargo build --release` and `docker build`: OK.
- Container smoke test, before vs after, against Redis with dummy AWS env: `/health` returns 200 with an identical body; `/metrics`
  returns 200 with identical metric names and types.
- Not exercised: live S3/DynamoDB/SNS TLS and IRSA (no AWS access), and OTLP span export (the service only sets up JSON tracing).

## Reproduce
```bash
trivy fs --scanners vuln --ignorefile /dev/null -f json -o before.json <demo-ciso checkout>/services/file-service/Cargo.lock
trivy fs --scanners vuln --ignorefile /dev/null -f json -o after.json services/file-service/Cargo.lock
docker build -t ow-file-service:after services/file-service && trivy image --scanners vuln --ignorefile /dev/null ow-file-service:after
```

## Limitation and operator steps (not executed)
These are local rebuilds. They are not proof of what ECR or `otterworks-ciso` on `otterworks-dev` runs; there were no AWS
credentials or kubeconfig. After merge to `demo-ciso`, `.github/workflows/cd-tenant.yml` rebuilds and deploys `t-ciso`.
Then, read-only:
```bash
# prerequisites: AWS creds for the ECR account (export AWS_ACCOUNT_ID); kube context otterworks-dev
export AWS_REGION=us-east-1 KCTX=otterworks-dev NS=otterworks-ciso
kubectl --context "$KCTX" -n "$NS" get deploy file-service -o jsonpath='{.spec.template.spec.containers[?(@.name=="file-service")].image}{"\n"}'
kubectl --context "$KCTX" -n "$NS" get pods -l app.kubernetes.io/name=file-service -o jsonpath='{range .items[*]}{.status.containerStatuses[0].imageID}{"\n"}{end}'
kubectl --context "$KCTX" -n "$NS" logs deploy/file-service --tail=50   # confirm S3/DynamoDB calls succeed over the new TLS stack
```
