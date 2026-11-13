# document-service: Python dependency CVEs (Trivy)

## Exposure, in plain words
The document-service image (FastAPI) carried 45 vulnerable Python package records (3 CRITICAL, 12 HIGH, 27 MEDIUM, 3 LOW):
- PyJWT 2.13.0 (1 CRITICAL, 6 HIGH, 7 MEDIUM): the library that checks every bearer token the service accepts.
- anyio 4.13.0 (1 CRITICAL) and certifi 2026.2.25 (1 CRITICAL, the CA trust bundle).
- starlette 0.37.2 (3 HIGH, 4 MEDIUM, 1 LOW): request parsing and multipart handling for every HTTP request.
- urllib3 2.7.0 (2 HIGH), used for outbound AWS/HTTP calls; protobuf 4.25.9 (HIGH), used by the OTLP exporter.
- idna, Mako, pydantic-settings, opentelemetry-api, setuptools.
- pip in both the system Python and the app venv.

## Fix
- `pyproject.toml` / `poetry.lock` (Poetry 1.8.2): FastAPI 0.162.6 (needed to reach Starlette 1.10.0), PyJWT 2.15.1, anyio 4.16.0,
  certifi 2026.10.23, idna 3.20, protobuf 6.33.6, pydantic-settings 2.16.3, urllib3 2.8.0, Mako 1.4.3, OpenTelemetry API/SDK/exporters
  1.45.1 + instrumentation 0.66b1, prometheus-fastapi-instrumentator 8.1.0, setuptools 84.2.1. The old `setuptools<81` cap is gone:
  instrumentation 0.66b1 no longer imports `pkg_resources`.
- `Dockerfile`: `pip uninstall -y pip` for the system Python and the venv. Nothing at runtime uses pip, and its vendored
  libraries carry their own CVEs. The apt line is unchanged (the zlib1g fix is tracked separately).
- `app/middleware/request_log.py`: one-line compatibility change. Starlette 1.x's internal middleware streaming response no
  longer subclasses `StreamingResponse`, so the middleware now checks for `body_iterator` instead.
- Tests added for the request-log plain, empty and streaming-error paths, and for JWT bad-signature/expired rejection.

## Results (same Trivy 0.71.0, same DB, `--scanners vuln --ignorefile /dev/null`, all severities)
| | total | CRITICAL | HIGH | MEDIUM | LOW | UNKNOWN | os-pkgs | Python |
|---|---|---|---|---|---|---|---|---|
| before `sha256:96b7b63aea54…` | 469 | 3 | 135 | 166 | 161 | 4 | 424 | 45 (44 fixable) |
| after `sha256:b32e6d6a179f…` | 424 | 0 | 123 | 139 | 158 | 4 | 424 | 0 |

Residual: 424 Debian 13.7 OS package records from `python:3.12-slim`. 3 are fixable (zlib1g CVE-2026-76844 HIGH, CVE-2026-85091 HIGH,
CVE-2026-27171 MEDIUM), and that fix is in a separate PR. The other 421 have no Debian fix available. No ignore file or skips were used.

Files: `trivy-document-service-summary.txt`, `trivy-document-service-{before,after}-python.txt` (raw Trivy table, library packages),
`trivy-document-service-{before,after}-findings.json` (all records extracted from the raw Trivy JSON).

## Reproduce
```bash
docker build -t ow-document-service:baseline <demo-ciso checkout>/services/document-service
docker build -t ow-document-service:after services/document-service
for t in baseline after; do trivy image --scanners vuln --ignorefile /dev/null -f json -o $t.json ow-document-service:$t; done
jq '[.Results[]?.Vulnerabilities[]?]|length' baseline.json after.json
```

## Behaviour checks
- `poetry run pytest -q`: 9 failed / 67 passed on unchanged demo-ciso, and 9 failed / 72 passed after (5 new tests). The same 9
  tests fail both times (8 unauthenticated requests expecting 200 get 401; `test_restore_version` hits `KeyError: -1`). These
  failures already exist on demo-ciso and this PR leaves them alone. `ruff check`: clean before and after.
- JWT in both images: valid HS256/HS384 accepted; bad signature and expired token rejected.
- Runtime smoke against throwaway Postgres 16, both images give identical results:
  - alembic migrations run 001→003;
  - `/health` returns 200 with database connected;
  - `/docs` and `/openapi.json` return 200 (15 paths);
  - authenticated create, get and list return 201, 200 and 200;
  - `/metrics` returns 200 and includes `http_requests_total`;
  - the request log captures exactly the wire bytes, with authorization redacted.

## Limitation
These are locally rebuilt images. They are **not** proof of what is deployed in ECR or in `otterworks-ciso` on `otterworks-dev`;
this audit had no AWS credentials or kubeconfig.

## Operator steps (not executed by this PR)
After review and merge into `demo-ciso`, `.github/workflows/cd-tenant.yml` (push to `demo-**`) builds the changed service and
deploys tenant `t-ciso`. Then verify read-only:
```bash
# prerequisites: AWS creds for the account that owns ECR (export AWS_ACCOUNT_ID), kube context for otterworks-dev
export AWS_REGION=us-east-1 KCTX=otterworks-dev NS=otterworks-ciso
kubectl --context "$KCTX" -n "$NS" get deploy document-service \
  -o jsonpath='{.spec.template.spec.containers[?(@.name=="document-service")].image}{"\n"}'
kubectl --context "$KCTX" -n "$NS" get pods -l app.kubernetes.io/name=document-service \
  -o jsonpath='{range .items[*]}{.status.containerStatuses[0].imageID}{"\n"}{end}'
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"
trivy image --scanners vuln --ignorefile /dev/null "<image@digest printed above>"
```
