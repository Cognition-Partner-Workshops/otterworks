# Branch locator: local platform run

## Runtime upgrade

Python 2.7 becomes Python 3.12 on the approved digest in `Dockerfile`.
Flask 1.1.4 becomes 3.1.3; Werkzeug 1.0.1 becomes 3.1.9;
requests 2.27.1 becomes 2.34.2; psycopg2-binary 2.8.6 becomes
psycopg[binary] 3.3.8. Flask resolves its supported Jinja2, MarkupSafe,
itsdangerous and click dependencies instead of the Python-2-era pins.
Gunicorn 26.2.0 replaces the development server and listens on 8080.
tzdata 2026.6 supplies IANA zones independently of the OS image.

`DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `GEO_URL` and `BRANCH_TZ`
are required environment settings; `DB_PORT` defaults to 5432. The password
comes from `secretEnv`, never from image settings. Templates stay beside
the application module; logs go to stdout/stderr. `/health` checks both
database and geocoder, returning 503 when either fails.

Opening hours use the configured IANA zone, not the host timezone. The
comparison baseline uses `Etc/UTC`. Decimal rounding of exact binary floats
with half-away-from-zero ties preserves Python 2's two-decimal distances.
Compact, sorted, ASCII JSON with its trailing newline preserves legacy
responses, including the missing-query error. The HTML template is unchanged.

## State and local fixtures

The application is stateless: PostgreSQL is external and read-only to
`branch_app`. Runtime UID/GID is 10001, root filesystem is read-only, and
only `/tmp` is writable. Gunicorn's optional control socket is disabled.

`deploy/kind-deps/seed.yaml` embeds exactly the bytes of the wave's
`data/seed.sql`; `geo-code.yaml` embeds the legacy geocoder stub. The kind
database initializes a separate role using the synthetic password from
`deploy/kind-secrets.env`, not the legacy `vm/db-roles.sql`. Local dependency
state is disposable (`emptyDir`); replacing the database pod reseeds it.
Production storage and credentials are supplied externally, not by these
throwaway dependencies. Never use the fixture passwords outside local tests.

## Pinned local gate

Run from the repository root. The standard worktree must be at
`18e3d4d3f2cec15ddff9261d3f1c6a5878085f1c`. Tools required: Docker,
kind, kubectl, Helm, conftest, and Python with PyYAML. No cloud access is
needed; the registry-shaped tag below is local only.

```bash
APP=industries/banking/vmware-wave-1/branch-locator
IMAGE=599083837640.dkr.ecr.us-east-1.amazonaws.com/otterworks/branch-locator
TAG=<unique-immutable-local-tag>
export KIND_CLUSTER=w1-branch-locator-r1
export OUT=$HOME/evidence/branch-locator/gate/run-N
mkdir -p "$OUT"
docker build --target test "$APP"
docker build -t "$IMAGE:$TAG" "$APP"
~/std/platform/standards/scripts/policy-check.sh "$APP" "$IMAGE" "$TAG"
kind create cluster --name "$KIND_CLUSTER" --wait 120s # only if absent
kubectl config use-context "kind-$KIND_CLUSTER"
bash "$APP/deploy/prepare-kind.sh"
~/std/platform/standards/scripts/kind-verify.sh "$APP" "$IMAGE" "$TAG"
```

The preparation step supplies dependency Secrets before the pinned script
waits for dependencies. The pinned script supplies the application's Secret.
Kind-only values use absolute service DNS names and `single-request-reopen`
to avoid intermittent resolver timeouts observed in this kind run.
Retain policy output and kind output from every attempt, including failures.
Keep `eks_deploy: false` and `BANK_W1_EKS` unset; do not push the image.

## Independent legacy baseline and parity

Do not rebuild `vm/Dockerfile` from this ported source: it deliberately still
describes the original host. Build it only from an `origin/demo-bank` worktree
(for this run, `~/legacy-src`). No `vm/` files were changed. The current legacy
container has no source bind mount, so edits here cannot change its code.
Keep Compose project `w1-branch-locator-vm-r1` running on loopback port 8083.
Its timezone is explicitly `Etc/UTC`; use the same zone on kind.

```bash
kubectl --context kind-w1-branch-locator-r1 port-forward \
  -n app-branch-locator svc/branch-locator 18083:80
# In another shell:
python3 ~/tools/industries/banking/vmware-wave-1/parity/run.py \
  --app branch-locator --vm-base http://127.0.0.1:8083 \
  --kind-base http://127.0.0.1:18083 \
  --output ~/evidence/branch-locator/locator-parity.json
```

Compare `/`, the six seeded place queries, and missing query (400). Locator
does not mutate state and has no business-day argument. Both sides use the
same seed and clock instant; run comparisons together away from an opening
boundary. The unit tests separately cover a timezone day/closing boundary.
The parity tool preserves raw hashes and canonicalizes only JSON key order
for locator. It does not normalize `open_now`, distances, or HTML whitespace.
