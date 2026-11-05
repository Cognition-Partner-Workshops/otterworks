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
database uses trust authentication and initializes `branch_app` with LOGIN
and SELECT only, without a password, not the legacy `vm/db-roles.sql`.
The app still receives `DB_PASSWORD` through `secretEnv` from the synthetic
fixture in `deploy/kind-secrets.env`, but the kind database does not verify
that password. This is strictly a throwaway local fixture, never production
authentication. Local dependency
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
export KIND_CLUSTER=w1-branch-locator-r2
export OUT=$HOME/evidence/branch-locator/gate/run-N
mkdir -p "$OUT"
docker build --target test "$APP"
docker build -t "$IMAGE:$TAG" "$APP"
~/std/platform/standards/scripts/policy-check.sh "$APP" "$IMAGE" "$TAG"
~/std/platform/standards/scripts/kind-verify.sh "$APP" "$IMAGE" "$TAG"
```

The pinned script creates the cluster and supplies the application's Secret.
Dependencies need no Secrets or manual preparation.
Kind-only values use absolute service DNS names and `single-request-reopen`
to avoid intermittent resolver timeouts observed in this kind run.
Retain policy output and kind output from every attempt, including failures.
Keep `eks_deploy: false` and `BANK_W1_EKS` unset; do not push the image.

## Independent legacy baseline and parity

`vm/legacy/requirements.txt` and `vm/legacy/app/` are byte-identical copies
from `origin/demo-bank`. `vm/Dockerfile` builds only those frozen Python 2.7
files, so the wave's `make vm-build` remains an independent legacy baseline.
The platform `Dockerfile.dockerignore` excludes all of `vm/` from its image
context. `vm/Dockerfile.dockerignore` allows only frozen legacy files into
the VM context. The fallback `.dockerignore` allows `vm/legacy/` for the
wave's classic-builder `DOCKER_BUILDKIT=0` VM builds, which do not support
Dockerfile-specific ignore files. The platform image copies only `app/`.
Use Compose project `w1-branch-locator-vm-r2` with an external Compose override
replacing the web port with `127.0.0.1:28083:5000` and setting `TZ=Etc/UTC`.
Its timezone is explicitly `Etc/UTC`; use the same zone on kind.

```bash
kubectl --context kind-w1-branch-locator-r2 port-forward \
  -n app-branch-locator svc/branch-locator 28084:80
# In another shell:
python3 ~/tools/industries/banking/vmware-wave-1/parity/run.py \
  --app branch-locator --vm-base http://127.0.0.1:28083 \
  --kind-base http://127.0.0.1:28084 \
  --output ~/evidence/branch-locator/locator-parity-r2.json
```

Compare `/`, the six seeded place queries, and missing query (400). Locator
does not mutate state and has no business-day argument. Both sides use the
same seed and clock instant; run comparisons together away from an opening
boundary. The unit tests separately cover a timezone day/closing boundary.
The parity tool preserves raw hashes and canonicalizes only JSON key order
for locator. It does not normalize `open_now`, distances, or HTML whitespace.
