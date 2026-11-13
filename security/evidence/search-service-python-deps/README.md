# search-service: Python dependency CVEs (Trivy)

## Exposure, in plain words
The search-service image shipped Python libraries with published vulnerabilities: urllib3 2.7.0 (2 HIGH), which the service
uses for every outbound HTTP call to MeiliSearch and AWS; Flask-Cors 4.0.2 (3 MEDIUM, CORS origin/path matching
weaknesses); requests 2.31.0 (3 MEDIUM, including leaking `.netrc` credentials and TLS-verification bypass on reused sessions);
Flask, marshmallow, python-dotenv and opentelemetry-api (1 each); and test-only/installer tooling that was installed in the
runtime image (pytest 8.1.1 and pip 25.0.1 with 6 pip CVEs).

## Fix
- `requirements.txt` / `requirements-dev.txt`: flask 3.1.3, flask-cors 6.0.5, marshmallow 3.26.2, requests 2.33.1,
  python-dotenv 1.2.2, opentelemetry-api/sdk 1.45.1 + opentelemetry-instrumentation-flask 0.66b1, pytest 9.0.3, urllib3 2.8.0.
- `Dockerfile`: `pip uninstall -y pip` after installing requirements. Nothing in the runtime image calls pip at runtime.
  Upgrading pip alone (26.2) was tried first; it removed the pip CVEs but brought in 9 new findings from pip's own vendored
  certifi/msgpack/urllib3/setuptools 70.3.0. Removing pip clears all of them.
- The Debian apt line is unchanged (the zlib1g fix is tracked separately).

## Results (same Trivy 0.71.0, same DB, `--scanners vuln --ignorefile /dev/null`, all severities)
| | total | os-pkgs | Python | fixable Python |
|---|---|---|---|---|
| before `sha256:e4e2fe66c33e…` | 444 | 424 | 20 | 20 |
| after `sha256:34f712ecdff9…` | 424 | 424 | 0 | 0 |

Residual: 424 Debian 13.7 OS package records from the `python:3.12-slim` base. Of these, 3 are fixable (zlib1g CVE-2026-76844
HIGH, CVE-2026-85091 HIGH, CVE-2026-27171 MEDIUM), and that fix is handled in a separate PR. The other 421 have no Debian fix
available yet. No ignore file or skips were used.

Files: `trivy-search-service-summary.txt` (versions, DB, image IDs, counts), `trivy-search-service-{before,after}-python.txt`
(raw Trivy table, library packages), `trivy-search-service-{before,after}-findings.json` (all records, both classes, extracted
from the raw Trivy JSON).

## Reproduce
```bash
docker build -t ow-search-service:baseline <demo-ciso checkout>/services/search-service
docker build -t ow-search-service:after services/search-service
for t in baseline after; do
  trivy image --scanners vuln --ignorefile /dev/null -f json -o $t.json ow-search-service:$t
done
jq '[.Results[]?.Vulnerabilities[]?]|length' baseline.json after.json
```

## Behaviour checks
- `python -m pytest --cov=app` (CI command): 41 passed, both before and after.
- CORS: the allowed origin `http://localhost:3000` gets `Access-Control-Allow-Origin` and other origins get none, with identical
  preflight headers before and after.
- Container: `/health` returns 200 `{"service":"search-service","status":"alive"}` for both images (MeiliSearch absent, startup
  deferred the same way). The service imports cleanly without pip.

## Limitation
These are locally rebuilt images. They are **not** proof of what is deployed in ECR or in `otterworks-ciso` on `otterworks-dev`;
this audit had no AWS credentials or kubeconfig.

## Operator steps (not executed by this PR)
After review and merge into `demo-ciso`, `.github/workflows/cd-tenant.yml` (push to `demo-**`) builds the changed service and
deploys tenant `t-ciso`. Then verify read-only:
```bash
# prerequisites: AWS creds for the account that owns ECR (export AWS_ACCOUNT_ID), kube context for otterworks-dev
export AWS_REGION=us-east-1 KCTX=otterworks-dev NS=otterworks-ciso
kubectl --context "$KCTX" -n "$NS" get deploy search-service \
  -o jsonpath='{.spec.template.spec.containers[?(@.name=="search-service")].image}{"\n"}'
kubectl --context "$KCTX" -n "$NS" get pods -l app.kubernetes.io/name=search-service \
  -o jsonpath='{range .items[*]}{.status.containerStatuses[0].imageID}{"\n"}{end}'
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"
trivy image --scanners vuln --ignorefile /dev/null "<image@digest printed above>"
```
