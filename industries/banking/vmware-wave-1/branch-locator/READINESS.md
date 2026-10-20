# branch-locator: wave-1 readiness

## 1. Summary

branch-locator is the public "find a branch" page: a ~55-line Flask app (`app/locator.py`) plus a pure-Python distance helper (`app/geo.py`). It takes a postcode or district, asks the internal geocoder for coordinates, reads the six rows of the `branches` table in `bankwave` and returns the three nearest with an `open_now` flag. On web-02 it runs on CentOS 7 with system Python 2.7 under systemd as root, with a hard-coded database password, absolute template and log paths, a geocoder name that only exists in `/etc/hosts`, the Flask development server on port 5000 and no health endpoint. None of that is hard to remove: the logic is stateless, has no Python 2-only syntax, and the existing unit tests already pass on Python 3.12. The work is a runtime port (Python 2.7 / Flask 1.1 to Python 3.12 / Flask 3), moving config and the secret out of `settings.py`, stdout logging, a `/health` route, a production WSGI server and the platform `Dockerfile` + `deploy/` files. The geocoder reachability from EKS and the owner/cost-center values need answers from outside the team.

**Verdict: replatform** (agrees with the manifest's `expected: replatform`).

## 2. Runtime and versions

| Layer | On the VM today | Source | Proposed target |
|---|---|---|---|
| OS | CentOS 7 (EOL 2024-06) | `HOST.md:5` | Debian bookworm via the approved base image |
| Language | system Python 2.7 (EOL 2020-01); stand-in `python:2.7.18-slim` | `HOST.md:5`, `vm/branch-locator.service:8`, `vm/Dockerfile:3` | Python 3.12 (see note) |
| Web framework | Flask 1.1.4, Werkzeug 1.0.1, Jinja2 2.11.3, MarkupSafe 1.1.1, itsdangerous 1.1.0, click 7.1.2 | `requirements.txt:1-6` | Flask 3.0.x with its matching Werkzeug/Jinja2/MarkupSafe/itsdangerous/click |
| HTTP client | requests 2.27.1 (last release supporting 2.7) | `requirements.txt:7` | requests 2.32.x |
| DB driver | psycopg2-binary 2.8.6 | `requirements.txt:8` | psycopg2-binary 2.9.x (keeps the `RealDictCursor` code unchanged) |
| Server / process manager | Flask dev server (`app.run`) under systemd `Restart=always` | `app/locator.py:55`, `vm/branch-locator.service:8-9` | gunicorn (2 sync workers) as PID 1; Kubernetes liveness/restart replaces systemd |
| Database | PostgreSQL `bankwave` on wave1-db (stand-in `postgres:16-alpine`; VM version not recorded) | `HOST.md:9`, `vm/compose.yaml:6` | PostgreSQL 15 (org target); the app only does one `SELECT` |
| Install | pip install globally, code under `/opt/branch-locator/app` | `HOST.md:5-6` | image with `/app`, deps in the image only |

**Base image:** `python-3.12-slim` from `base-images.yaml`
(`docker.io/library/python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1`) for both the `test` stage and the final stage, the same pattern as `examples/sample-service/Dockerfile`.

**Note on the Python version:** the `modernization-target-standard` skill names Python 3.11, but `base-images.yaml` approves only `python:3.12-slim`, and BASE-01 rejects anything else. The platform gate decides here, so the proposal is Python 3.12. If the target has to be 3.11, the platform team must first add a pinned 3.11 image through a PR to the standards. The code has no feature that differs between 3.11 and 3.12. The existing unit tests passed on Python 3.12.13 on this VM (see section 5).

## 3. Host ties

The manifest lists four conditions for this app. Rows marked **NEW** are ones the manifest does not list. All line numbers were checked with `grep -n`/`nl -ba` on commit e42786c9. Paths are relative to `industries/banking/vmware-wave-1/branch-locator/`.

| id | What the host gives the app | file:line | Platform rule it breaks | In manifest |
|---|---|---|---|---|
| H1 credential-in-source | Database password as a literal in the code | `app/settings.py:5` (the same value is also created in the wave-level `vm/db-roles.sql:2`) | Secrets as references only (README "Application requirements"); Trivy `platform-hardcoded-db-password` matches `DB_PASSWORD = "..."`; would become SECRET-01/03/04 if moved naively into `env`, a ConfigMap or `ENV` | yes |
| H2 host-path (templates) | Templates at an absolute install path | `app/settings.py:9`, `app/locator.py:16` | Config from env/mounted files; breaks as soon as the image layout is not `/opt/branch-locator` | yes |
| H3 host-path + file logging | Log file under `/var/log/branch-locator`, created by the host (stand-in `mkdir`) | `app/settings.py:10`, `app/locator.py:12-13`, `vm/Dockerfile:5`, `HOST.md:10` | "Logs on stdout/stderr, no log file"; SEC-02 (read-only root fs). `basicConfig(filename=...)` runs at import, so on a read-only root the process dies before it serves anything | path yes; **NEW**: the file-logging and read-only-root crash are not called out |
| H4 name-resolution | `geo.bank.internal` resolved only through `/etc/hosts` to 10.40.2.17 | `vm/etc-hosts:3`, `app/settings.py:7`, `HOST.md:8` | Config from env; pod `/etc/hosts` is not managed; egress must be reachable from EKS | yes |
| H5 eol-runtime | CentOS 7 + system Python 2.7, 2020-era pins, global pip | `requirements.txt:1-8`, `vm/Dockerfile:3`, `vm/branch-locator.service:8`, `HOST.md:5` | BASE-01 (no approved 2.7 image; `python:2.7.18-slim` is neither approved nor digest-pinned); Trivy CRITICAL CVEs in an EOL Debian base are likely | yes |
| H6 hard-coded DB endpoint | DB host, name and user as literals | `app/settings.py:2-4` | Config from env/mounted files | **NEW** |
| H7 no health endpoint | Only `/` and `/api/nearest`; `/health` returns 404 on the stand-in | `app/locator.py:37-51` | PROBE-01 / "`/health` answers 200". The chart renders probes on `/health`, so conftest passes but readiness never goes green on kind and the smoke fails | **NEW** |
| H8 runs as root | systemd unit has no `User=`; stand-in has no `USER`; stand-in `id` shows uid 0 | `vm/branch-locator.service:6-9`, `vm/Dockerfile:3-9` | BASE-02, SEC-01 | **NEW** |
| H9 process manager + dev server | systemd `Restart=always` restarts it; Werkzeug dev server on `0.0.0.0` | `vm/branch-locator.service:9`, `app/locator.py:55` | PROBE-01 (liveness replaces `Restart=always`); the dev server is not a production server (single process, no worker timeouts) | **NEW** |
| H10 fixed port | Port 5000 hard-coded; chart default `containerPort` is 8080 | `app/settings.py:12`, `app/locator.py:55`, `vm/Dockerfile:8` | Config from env (`containerPort`/probe port must match) | **NEW** |
| H11 host timezone | `open_now` uses naive `datetime.now()`, i.e. the host clock and zone | `app/locator.py:48` | No README rule; containers run `Etc/UTC` (stand-in shows `Etc/UTC`). If web-02 runs in the bank's local zone, `open_now` changes after the move. This is a parity risk | **NEW** |
| H12 plaintext transport | Geocoder over `http://`; DB connection without `sslmode` | `app/settings.py:7`, `app/locator.py:20-21` | No gate rule; needs a decision for the shared cluster (NetworkPolicy egress, TLS to RDS) | **NEW** |
| H13 config edited on the box | "`app/settings.py`, edited on the box when something changes" | `HOST.md:7` | Config from env/mounted files; with an immutable image, every change has to go through the chart values | **NEW** |

Host ties: **13** (4 listed in the manifest, 9 new or only partly covered).

## 4. Changes to meet platform/standards

In this order:

1. **Characterization tests first** (section 5). Capture the golden responses from the stand-in before touching code.
2. **Port to Python 3.12 and current pins**: Flask 3.0.x, requests 2.32.x, psycopg2-binary 2.9.x, plus gunicorn. Jinja2 2.11 and MarkupSafe 1.1.1 do not install or import on 3.12, so the whole Flask stack moves together. No source syntax changes are expected; `geo.py` already runs on 3.12.
3. **Config from env**: replace `settings.py` literals with `os.environ` reads: `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` (required, no default), `GEO_URL`, `PORT` (default 8080), optional `DB_SSLMODE`. The template folder becomes relative to the module (`Flask(__name__)` default `templates/`), so H2 goes away.
4. **Secret via `secretEnv`**: `secretEnv: {DB_PASSWORD: {secret: branch-locator-db, key: password}}`, filled by External Secrets from AWS Secrets Manager. Rotate the `branch_app` password, because the current value is in git history in two files (`app/settings.py:5`, `vm/db-roles.sql:2`). For kind, put a test-only value in `deploy/kind-secrets.env`.
5. **Stdout logging**: `logging.basicConfig(stream=sys.stdout, ...)`; gunicorn access/error logs to `-`. Remove the `/var/log` path.
6. **`/health`**: return 200 when the process is up. Optionally run a `SELECT 1` against the DB with a short timeout for readiness. Because the chart wires one path to both probes, keep it cheap and do not call the geocoder, otherwise a geocoder outage restarts pods.
7. **Process model**: `CMD ["gunicorn", "-b", "0.0.0.0:8080", "-w", "2", "--access-logfile", "-", "locator:app"]`; no systemd, no `Restart=always`.
8. **Timezone**: compute `open_now` in an explicit zone (`zoneinfo.ZoneInfo(os.environ.get("BRANCH_TZ", ...))`) once the VM's zone is confirmed (H11). Base images have no tzdata for `zoneinfo` keys beyond UTC unless `tzdata` is pip-installed, so add the `tzdata` wheel.
9. **Geocoder**: `GEO_URL` from values. Ask for a DNS record for `geo.bank.internal`, or use a Kubernetes `ExternalName`/selector-less Service + Endpoints to 10.40.2.17. Confirm routing from the EKS VPC and allow egress in the NetworkPolicy.
10. **Dockerfile** at the app root (the `vm/Dockerfile` stays as the stand-in):
    - stage `test`: `FROM <python-3.12-slim@digest> AS test`, install `requirements.txt` and test deps, copy `app/` and `tests/`, `RUN python -m pytest -q` (or `python -m unittest discover -s tests`).
    - final: same pinned base, `pip install --no-cache-dir -r requirements.txt`, `COPY --from=test` the app only, `ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1` (no credential-like names in `ENV`/`ARG`, SECRET-04), `USER 10001`, `EXPOSE 8080`.
11. **Read-only root fs**: `writablePaths: [/tmp]` (gunicorn worker heartbeat files go to `/tmp`; with `PYTHONDONTWRITEBYTECODE` nothing else is written).
12. **`deploy/values.yaml`**: `app: branch-locator`, `owner: <team>`, `costCenter: <code>` (to be supplied), `workload: web` (a **Deployment**, not a CronJob: this is a long-running request/response service), `containerPort: 8080`, `env` for DB_HOST/DB_NAME/DB_USER/GEO_URL/BRANCH_TZ, the `secretEnv` above, default resources (requests 100m/128Mi, limits 500m/256Mi: enough for a 2-worker gunicorn), `replicas: 2` (stateless, no session state), `ingress.enabled: true` with the public host. The page uses a relative `api/nearest` URL (`app/templates/index.html:10`), so path-prefix ingress also works.
13. **`deploy/platform.yaml`** smoke paths: `/health` 200, `/` 200, `/api/nearest?q=harbour` 200, `/api/nearest` 400. Add `deploy/kind-deps/` with a PostgreSQL 15 loaded with the `branches` rows from `data/seed.sql:5,299-304` and the role grant, plus the geocoder stub (`vm/geo-stub/geo_stub.py`), and `deploy/values-ci.yaml` pointing DB_HOST/GEO_URL at them.
14. Delete `settings.py` or reduce it to env reads, and update `HOST.md`'s successor runbook.

**First pipeline run (app as it is today) would fail:**
- *Unit tests*: there is no `Dockerfile` in the app directory (only `vm/Dockerfile`), so `docker build --target test` fails at once. Even with `vm/Dockerfile` copied up, it has no `test` stage.
- *Policy gate (Dockerfile)*: BASE-01 (`python:2.7.18-slim`, not approved, no digest) and BASE-02 (no `USER`).
- *Policy gate (manifest)*: `render.sh` cannot render because `deploy/values.yaml` is missing (`app`, `owner`, `costCenter` are `required` in `_helpers.tpl`).
- *Trivy*: likely CRITICAL CVEs in the EOL Python 2.7/Debian base (not run here; Trivy is not installed on this VM). See the risk in section 8 about the HIGH-severity secret rule.
- *kind runtime* (once the above are fixed but before code changes): SEC-02 read-only root makes `logging.basicConfig` fail at import (H3), and `/health` 404s, so readiness never passes and the smoke fails (H7). Port 5000 vs chart port 8080 also breaks probes and Service (H10).

## 5. Test strategy

**What was run on this VM (about 5 minutes):**
- `python3 -m unittest discover -s tests -v` on Python 3.12.13: 3/3 pass (`test_distance_one_tenth_degree`, `test_nearest_sorted_and_limited`, `test_closed_at_closing_time`).
- Stand-in: `docker compose -f vm/compose.yaml up -d --build wave1-db geo web-02` (only branch-locator and its dependencies instead of the full `make vm-up`; Docker Hub returned 429, so `python:3.12-slim`, `postgres:16-alpine` and `python:2.7.18-slim` were pulled from `mirror.gcr.io` and retagged). Results at 22:53 UTC (all `open_now=false`, the container clock is UTC):

| Request | Status | Top 3 (km) |
|---|---|---|
| `/api/nearest?q=harbour` | 200 | Harbour Point 0.25, Market Square 2.97, Hillcrest 5.36 |
| `q=market` | 200 | Market Square 0.25, Harbour Point 2.63, Riverside 2.97 |
| `q=old town` | 200 | Old Town 0.4, Lakeview 4.32, Harbour Point 5.4 |
| `q=river` | 200 | Riverside 0.16, Market Square 2.57, Harbour Point 5.35 |
| `q=hill` | 200 | Hillcrest 0.49, Harbour Point 5.11, Old Town 7.37 |
| `q=lake` | 200 | Lakeview 0.35, Old Town 4.18, Riverside 5.23 |
| `q=zzz` (stub fallback 10.0,-30.0) | 200 | Harbour Point 2.66, Old Town 3.1, Market Square 3.88 |
| `/api/nearest` (no q) | 400 | `{"error":"q is required"}` |
| `/` | 200 | HTML form |
| `/health` | 404 | (no route) |
| geocoder stopped | 500 | Werkzeug HTML error |
| database stopped | 500 | traceback goes to the log file only |

**Characterization tests (before any change):** a pytest module (e.g. `tests/characterization/test_http.py`, `BASE_URL` default `http://localhost:8083`) run against `make vm-up` in `industries/banking/vmware-wave-1` on the shared seed (`data/seed.sql`). It pins:
- the full JSON body for each of the seven queries above (parsed and compared, key order ignored), including `lat`/`lon` floats, `km` rounding to 2 dp, `query` echo, branch order and the address/opens/closes fields;
- `400` + body for missing/blank `q` (`q=%20` is stripped to empty);
- `/` returns 200 with `text/html` and the form and script present;
- `open_now` checked against a value computed in the test from the same clock and zone, plus the boundary rule (`opens <= now < closes`) through the existing `geo.is_open` tests;
- error behavior: 500 when the geocoder or DB is down (status only; the body is an accepted difference).
Keep the passing output from the VM run as the "before" artifact. The same tests run unchanged against the replatformed app (docker run locally, then the kind port-forward).

**Unit tests to `test` stage:** the existing `tests/test_geo.py` runs in the `test` stage (`python -m pytest -q tests` or `unittest discover`). Add unit tests for config loading (missing `DB_PASSWORD` fails fast), `/health`, and `api_nearest` with the geocoder and DB mocked, so the stage needs no network or database.

**Parity report rows (before vs after):**

| Check | Before (VM stand-in) | After |
|---|---|---|
| JSON body for harbour/market/old town/river/hill/lake/zzz | golden files from the run above | identical |
| `/api/nearest` without q | 400 + error body | identical |
| `/` status and content type | 200 text/html | identical |
| `open_now` at a fixed instant in the business zone | computed from VM zone | identical (or an accepted difference if the VM zone is UTC and the target sets BRANCH_TZ) |
| geocoder down / DB down | 500 / 500 | 500 / 500 (body accepted difference) |
| `/health` | 404 | 200 (accepted difference: new endpoint) |
| log line `nearest q=... -> [...]` | in `/var/log/branch-locator/app.log` | on stdout (accepted difference: location) |
| process user | uid 0 | uid 10001 |

**kind smoke paths** (`deploy/platform.yaml`): `/health` 200, `/` 200, `/api/nearest?q=harbour` 200 (needs `kind-deps` PostgreSQL with the seed branches and the geo stub), `/api/nearest` 400.

## 6. Effort estimate

**S/M: 4-7 engineer-days.**

| Work item | Days |
|---|---|
| Characterization tests against the stand-in + golden files | 0.5-1 |
| Python 3.12 / Flask 3 port, dependency pins, gunicorn | 0.5-1 |
| Env config, stdout logging, `/health`, timezone handling, new unit tests | 0.5-1 |
| Dockerfile (`test` stage, pinned bases, USER), `deploy/values.yaml`, `values-ci.yaml`, `platform.yaml`, `kind-deps` (PostgreSQL 15 + geo stub), `kind-secrets.env` | 1-1.5 |
| Secret: Secrets Manager entry, ExternalSecret, rotate `branch_app` password | 0.5-1 |
| Geocoder reachability (DNS record or ExternalName/Endpoints, egress policy) | 0.5-1 |
| Pipeline iterations, parity report, PR review | 0.5-1 |
| **Total** | **4-7** |

Assumptions: the geocoder at 10.40.2.17 can be reached from the EKS VPC (or a DNS record can be made) without a network project. External Secrets and a ClusterSecretStore already exist on the cluster. The database stays where it is, or moves to the shared RDS as a separate wave item (not costed here). Owner and cost-center codes are supplied. No functional changes beyond the timezone fix.

## 7. Verdict

**replatform.** This is a small, stateless request/response service with no session state, no NFS, no cron and no web-server modules. Its only dependencies are one read-only table and one HTTP call. Every host tie can be removed with config and packaging changes plus a mechanical runtime upgrade. The business logic (`geo.py`) carries over unchanged and is already covered by unit tests that pass on 3.12. A rewrite would add nothing, and retaining it means keeping CentOS 7 and Python 2.7 (both EOL) on a public-facing page. I **agree** with the manifest's `expected: replatform`. The manifest understates the scope, though: it lists 4 conditions and misses the missing `/health`, root user, dev server/systemd restart, fixed port, host timezone and plaintext transport.

## 8. Risks and open questions

- **Biggest blocker:** the database password is committed at `app/settings.py:5`, and the same value is created in `vm/db-roles.sql:2`. It has to move to a `secretEnv` reference filled by External Secrets and be rotated, because it is in git history. That depends on whoever owns Secrets Manager and the database role.
- **Trivy severity gap (unverified):** the pipeline runs `trivy image --severity CRITICAL`, while the platform secret rules in `policy/trivy/secret-rules.yaml` are `severity: HIGH`. A hard-coded DB password in a settings file may therefore not fail the Trivy step. Do not rely on the gate to catch H1; remove it by design. Worth raising with the platform team. Not verified, because Trivy is not installed on this VM.
- **Timezone of web-02:** unknown. If it is local time, `open_now` shifts by the UTC offset after the move unless BRANCH_TZ is set. All seeded branches open 08:30-16:30.
- **Geocoder:** is 10.40.2.17 reachable from EKS, is there a TLS endpoint, and who owns it? It has no DNS record today.
- **Python 3.11 vs 3.12:** the skill says 3.11, the approved base list only has 3.12. This note follows the gate (3.12).
- **Database target:** does `bankwave` stay on wave1-db or move to RDS PostgreSQL 15? TLS (`sslmode=require`) to RDS needs the CA bundle in the image or a mounted file.
- **Per-request DB connection** (`app/locator.py:20`) with 2 replicas x 2 workers is fine for six rows but has no pool or timeout. Add `connect_timeout` so a DB outage does not pin workers.
- **XSS in the page:** `app/templates/index.html:14` builds HTML with `innerHTML` from DB fields. This is not a host tie, but it is a public page; consider `textContent` in the same change (a behavior-neutral fix the parity check will show as identical).
- **Owner and cost-center** values for `deploy/values.yaml` are not recorded anywhere in the repo.
- **kind-deps images and Kyverno REG-01:** the throwaway PostgreSQL and geo stub images must either come from the approved ECR prefix or run outside the enforced namespace. Check how `kind-verify.sh` scopes Kyverno before writing `kind-deps/`.
- **DeepWiki:** asked about `branch-locator` / `industries/banking/vmware-wave-1` and the platform standards. It had no information on the app and did not know `base-images.yaml`, conftest/Kyverno or the rule ids (the index predates both branches). It only described the existing `infrastructure/helm/*` charts. This note is based on the code.
- **Standards location:** ESTATE.md says the standards are on `main`; they are only on `devin/1792540800-platform-standards` (c56cbe8f). The app should pin that commit, or its successor on `main`, as `standards_ref`.
