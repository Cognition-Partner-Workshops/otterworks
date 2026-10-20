# notify-svc: wave-1 readiness

## 1. Summary

`notify-svc` is a small Express service (one 46-line `server.js`, one template module) that renders customer notification text and queues it in Redis for the SMS and push gateways. On notify-01 and notify-02 it runs on Node 12 under PM2 in cluster mode, with a password-less `redis-server` on the same box holding the per-account rate-limit counters and outboxes. The application logic is portable and already logs to stdout; what ties it to the host is the runtime (Node 12 on Ubuntu 18.04), PM2 as the only runbook (two workers, a 03:30 restart, a 300M memory ceiling, file logs), a hard-coded port, the local unauthenticated Redis and the per-host state it holds, a missing `/health` endpoint and running as root. All of these are fixable with configuration and a few lines of code; the real work is choosing a managed Redis and agreeing with the gateways how they drain the outbox once the two per-host Redis instances become one.

**Verdict: replatform** (agrees with the manifest's `expected: replatform`). Effort: **M: 6-10 engineer-days**.

## 2. Runtime and versions

| Item | On the VM today | Source | Target |
|---|---|---|---|
| OS | Ubuntu 18.04 (EOL) | `HOST.md:5` | Debian 12 via the approved Node base |
| Runtime | Node 12.x from NodeSource (EOL 2022-04); stand-in runs v12.22.12 | `package.json:11-13`, `HOST.md:5`, `vm/Dockerfile:2` | Node 20 (`node-20-slim`, see below) |
| Process manager | PM2 4.5 global, `pm2 start ecosystem.config.js --env production` + `pm2 save`; stand-in pm2 4.5.6 under `pm2-runtime` | `HOST.md:6`, `ecosystem.config.js:1-22`, `vm/Dockerfile:4,11` | none: one `node src/server.js` per container, Kubernetes restarts and scales |
| Framework | express 4.17.1 (lockfile: body-parser 1.19.0) | `package.json:15`, `package-lock.json` | express 4.21.x (latest 4.x, same API) |
| Redis client | redis 3.1.2 (redis-parser 3.0.0) | `package.json:16` | redis 3.1.2 kept for parity in the first cut (works on Node 20); move to node-redis 4.x/ioredis as a follow-up |
| Data store | local `redis-server` on each box, default port 6379, no password; stand-in copies the redis 6.2 binary | `HOST.md:8`, `vm/Dockerfile:3,11` | managed Redis-compatible store (ElastiCache Redis OSS/Valkey 7.x) with AUTH + TLS; throwaway Redis in `deploy/kind-deps/` for the kind run |
| Tests | `node test/templates.test.js` (4 assertions, plain `assert`) | `package.json:9`, `test/templates.test.js` | same command in the `test` stage, plus characterization tests |

**Base image.** `base-images.yaml` has exactly one Node entry, `node-20-slim`:
`docker.io/library/node:20-bookworm-slim@sha256:2cf067cfed83d5ea958367df9f966191a942351a2df77d6f0193e162b5febfc0`. Use it for both the `test` stage and the runtime stage. Note that Node 20 itself reached end of life on 2026-04-30, so this is the only approved choice today but not a long-term one; ask the platform team to add a Node 22 or 24 LTS entry (see Risks). The `modernization-target-standard` skill lists no Node target version, so the approved base decides it.

## 3. Host ties

All paths are relative to `industries/banking/vmware-wave-1/notify-svc/`; line numbers verified with `nl -ba` on commit e42786c. "Manifest" = listed in `complexity-manifest.json` for notify-svc (`process-manager-runbook`, `fixed-port`, `local-dependency`, `eol-runtime`); **NEW** = not listed there.

| Id | What the host gives the app | file:line | Platform rule it breaks | Manifest |
|---|---|---|---|---|
| H1 | PM2 supervises the process and forks two cluster workers per box (and two boxes, notify-01/02); `ecosystem.config.js` is the only record of how it runs | `ecosystem.config.js:1-2,10-11`; `HOST.md:6`; `vm/Dockerfile:4,11` | one process per container; scaling becomes `replicas` (no rule id; PROBE-01/RES-01 assume one process) | Manifest (`process-manager-runbook`) |
| H2 | Nightly restart at 03:30 host-local time (PM2 `cron_restart`) | `ecosystem.config.js:13`; `HOST.md:6` | no in-container cron; Deployment, not CronJob | Manifest (`process-manager-runbook`) |
| H3 | Logs written to `/var/log/notify/out.log` and `err.log` on local disk | `ecosystem.config.js:14-16`; `vm/Dockerfile:4`; `HOST.md:6` | "Logs on stdout and stderr"; SEC-02 (read-only root fs) | Manifest (`process-manager-runbook`) |
| H4 | Memory ceiling of 300M per worker enforced by PM2 (`max_memory_restart`) | `ecosystem.config.js:12` | RES-01 (limit range 256Mi; 300M is above it) | **NEW** |
| H5 | Absolute install path `/opt/notify-svc` as working directory | `ecosystem.config.js:9`; `HOST.md:6`; `vm/Dockerfile:5` | configuration from env / mounted files (low impact, the code uses relative `require`s) | **NEW** |
| H6 | Port 3000 hard-coded, no `PORT` env | `src/server.js:7,46`; `HOST.md:7` | configuration from environment variables; must match chart `containerPort` | Manifest (`fixed-port`) |
| H7 | Redis on 127.0.0.1:6379, no password, no TLS: `redis.createClient()` with no arguments | `src/server.js:10`; `ecosystem.config.js:3`; `HOST.md:8`; `vm/Dockerfile:3,11` | configuration from env; once a password exists it must be a `secretEnv` ref (SECRET-01, SECRET-04) | Manifest (`local-dependency`) |
| H8 | Per-host state: rate-limit counter `notify:rate:<account>` (20/hour, TTL 3600 s) and outbox list `notify:outbox:<account>` live in the box's own Redis, so each VM has its own outbox and its own rate budget | `src/server.js:8,25-31,40`; `HOST.md:8` | stateless pods (same class as session affinity): replicas must share one store; durability of queued messages | **NEW** (manifest only says "Redis on localhost") |
| H9 | No health endpoint; only `POST /notify` and `GET /outbox/:account` exist (stand-in: `GET /health` returns 404) | `src/server.js:16,39` | PROBE-01 (chart wires `/health` to both probes; pod never becomes Ready) | **NEW** |
| H10 | Node 12 runtime (EOL) | `package.json:11-13`; `HOST.md:5`; `vm/Dockerfile:2` | BASE-01 (`node:12-bullseye` is not in `base-images.yaml`) | Manifest (`eol-runtime`) |
| H11 | Ubuntu 18.04 with NodeSource packages and a globally installed PM2 (EOL OS) | `HOST.md:5`; stand-in `vm/Dockerfile:2,4` | BASE-01 | **NEW** |
| H12 | Runs as root (no `USER`; stand-in `id` = uid 0, PM2 user `root`) | `vm/Dockerfile:1-11` (no `USER` line) | BASE-02, SEC-01 | **NEW** |
| H13 | Redis server binary shipped next to the app and started by the same shell (two processes in one image) | `vm/Dockerfile:3,11` | BASE-01 in spirit (the `COPY --from=docker.io/library/redis:6.2-bullseye` pulls an unapproved image; `dockerfile.rego` only checks `FROM`, so the gate would not catch it) | **NEW** |
| H14 | Network position is the only access control: plain HTTP, no authentication on either endpoint; `GET /outbox` returns the full unmasked account id | `src/server.js:13-14,30,39-43,46` | NET-01 (ClusterIP behind ingress-nginx, chart NetworkPolicy); keep `ingress.enabled: false` | **NEW** |
| H15 | Graceful stop and reload come from PM2; the app has no SIGTERM handler and never closes the server or Redis client | `src/server.js:46` (only `app.listen`) | none directly; needed for rolling updates without dropped requests | **NEW** |
| H16 | Dated libraries: express 4.17.1 (2019) and redis 3.1.2 with known advisories in the express dependency tree | `package.json:15-16` | Trivy image scan stage (`--severity CRITICAL --ignore-unfixed`) is a risk, not a certain fail | **NEW** |

Checked and not a tie: timestamps use `new Date().toISOString()` (UTC, `src/server.js:30`), so the box timezone only affects the 03:30 restart (H2); no TLS keystore, no NFS, no LDAP, no HTTP session, no cron outside PM2, no web-server modules, no credentials in the source (the stand-in Redis has none either). Nothing else in the wave calls notify-svc or is called by it (`grep -rn notify` outside the folder only hits `Makefile:13,34-35`, `vm/compose.yaml:74-80`, `ESTATE.md:10`, the manifest), and it does not use `data/seed.sql` or the database.

**Count: 16 host ties, 11 of them not in the manifest** (H4, H5, H8, H9, H11-H16).

## 4. Changes to meet platform/standards

In order; each step keeps the characterization tests (section 5) green.

1. **Pin behavior first.** Add the characterization suite and run it against the stand-in; keep its output as the "before" column.
2. **Config from env** (`src/server.js:7,10`): `PORT` (default 3000 so behavior and the stand-in mapping stay the same), `REDIS_URL` (default `redis://127.0.0.1:6379`), `REDIS_PASSWORD` and `REDIS_TLS` passed to `redis.createClient({ url, password, tls })`. Keep `LIMIT_PER_HOUR = 20` as code; it is business behavior.
3. **`/health`** that returns 200 only when the Redis client is connected and a `PING` answers within a short timeout, 503 otherwise. The chart wires it to readiness and liveness (`helm/app/values.yaml` `probes.path: /health`). Consider a liveness that does not depend on Redis (e.g. `?live=1`) so a Redis blip does not restart every pod; the chart today uses one path for both, so the first cut uses `/health` for both.
4. **SIGTERM handling**: close the HTTP server, then `db.quit()`, exit 0 (replaces PM2 graceful reload, H15).
5. **Runtime bump**: `engines.node` to `20.x`, express to 4.21.x, regenerate `package-lock.json` (`npm ci` must work on Node 20). `npm test` already passes on a newer Node (ran on v24.19.0: "templates: 4 assertions passed").
6. **Dockerfile at the app root** (not `vm/Dockerfile`, which stays as the VM stand-in):
   - stage `test`: `FROM docker.io/library/node:20-bookworm-slim@sha256:2cf067cf...c0 AS test`, `npm ci`, copy `src` and `test`, `RUN npm test` (later also the in-process characterization tests).
   - final stage: same digest, `npm ci --omit=dev`, copy `src` only, `ENV NODE_ENV=production`, `USER 10001` (numeric, matches chart `securityContext.runAsUser`), `EXPOSE 3000`, `CMD ["node", "src/server.js"]`. No PM2, no `redis-server`, no `ENV`/`ARG` whose name matches `password|secret|token` (SECRET-04).
   - `.dockerignore` excluding `vm/`, `deploy/`, `node_modules`, so `kind-secrets.env` can never land in the image (Trivy secret scan).
7. **Stdout logging**: nothing to change in code (`console.log`/`console.error` already, `src/server.js:11,33,46`); dropping PM2 removes the `/var/log/notify` files (H3).
8. **Read-only root fs**: the app writes nothing at runtime; keep the chart default `writablePaths: [/tmp]` as the only emptyDir.
9. **Resources**: requests 100m/128Mi, limits 500m/256Mi (chart defaults). The stand-in workers use about 44 MB each; set `NODE_OPTIONS=--max-old-space-size=192` in `env` so V8 stays under the 256Mi limit that replaces PM2's 300M (H4).
10. **Workload type: Deployment** (`workload: web`), `replicas: 2` to match two VMs; the 03:30 restart is dropped (no CronJob), memory pressure is handled by the limit and liveness. If the restart is hiding a leak, the characterization soak (section 5) should show it.
11. **Redis replacement**: one shared managed Redis (ElastiCache Redis OSS/Valkey, AUTH + in-transit TLS) per environment, provisioned outside the chart; its password in AWS Secrets Manager, surfaced by External Secrets as Secret `notify-svc-redis`; `secretEnv: {REDIS_PASSWORD: {secret: notify-svc-redis, key: password}}`. Moving from two per-host Redis instances to one store changes two behaviors that must be accepted explicitly: the rate limit becomes 20/hour per account globally instead of per box, and the gateways see a single outbox instead of two (H8). Cut-over needs the old outboxes drained.
12. **`deploy/values.yaml`**: `app: notify-svc`, `owner: <owning team>`, `costCenter: <finance code>`, `containerPort: 3000`, `replicas: 2`, `env: {REDIS_URL: ..., REDIS_TLS: "true", NODE_OPTIONS: ...}`, `secretEnv` as above, `ingress.enabled: false` (internal service; gateways reach it in-cluster).
13. **`deploy/platform.yaml`** smoke paths (the kind smoke is GET-only): `/health` expect 200, `/outbox/HG611000001` expect 200 (empty list on a fresh Redis), `/notify` expect 404 (GET on a POST route, as on the VM).
14. **kind run files**: `deploy/kind-deps/redis.yaml` (Redis Deployment + Service in the `deps` namespace, with `requirepass`), `deploy/values-ci.yaml` (`REDIS_URL=redis://redis.deps.svc.cluster.local:6379`, `REDIS_TLS: "false"`), `deploy/kind-secrets.env` with a test-only `notify-svc-redis.password=...`.

**What the first pipeline run would fail, today, pointed at `notify-svc/`:**
- *Unit tests* fail at once: there is no `Dockerfile` in the app directory (only `vm/Dockerfile`), so `docker build --target test` errors; *Container build* fails for the same reason, and Trivy, SBOM, the policy gate and kind are skipped.
- If `vm/Dockerfile` were simply moved up: unit still fails (no `test` stage); conftest fails **BASE-01** (`docker.io/library/node:12-bullseye` not approved/digest-pinned) and **BASE-02** (no `USER`); the manifest gate fails to render (`app is required`, no `deploy/values.yaml`), so LABEL-01 cannot even be evaluated; Trivy on a Node 12 / bullseye image is likely to fail on CRITICAL fixed CVEs (not verified).
- After steps 6 and 12-14 but **without** steps 2-3: conftest passes (the chart adds probes), but on kind the pod never becomes Ready because `/health` is 404 (**PROBE-01** in practice) and Redis is not on localhost, so `helm --wait` times out and the runtime stage fails. The manifest does not predict this failure for notify-svc.

## 5. Test strategy

**Characterization tests first** (org standard): pin the current behavior against the running stand-in, keep the passing output, and run the same tests unchanged against the replatformed service.

- **Before target**: `make vm-build && make vm-up` in `industries/banking/vmware-wave-1`, notify-svc at `http://localhost:8084/` (`ESTATE.md:10`, `HOST.md:11`, `vm/compose.yaml:74-80`); `make vm-smoke` sends one `statement_ready`. **After target**: the new image with a throwaway Redis (`docker run` locally) and the kind port-forward from `kind-verify.sh`.
- **Inputs**: seed accounts from `data/seed.sql` (24 accounts, `HG611000001` ... `HG841000024`) and the three kinds in `src/templates.js:3-7`. Compare bodies with the `at` timestamp removed (pattern-checked as ISO-8601 UTC instead).
- **Cases** (all ran against the stand-in on this commit, results below are the "before" values):

| # | Request | Before (stand-in) |
|---|---|---|
| C1 | `POST /notify` HG611000001 `statement_ready`, `fields:{}` | 202 `{"queued":true,"text":"Your statement for ****0001 is ready to view."}` |
| C2 | `POST /notify` HG611000001 `card_payment` amount 12.40, merchant Corner Cafe | 202 `...Card payment of 12.40 on ****0001 at Corner Cafe.` |
| C3 | `card_payment` with `fields:{}` | 400 `{"error":"missing field: amount"}` |
| C4 | unknown kind `nope` | 400 `{"error":"unknown notification kind: nope"}` |
| C5 | no `account` | 400 `{"error":"account and kind are required"}` |
| C6 | `GET /outbox/HG611000001` after C1-C2 | 200, newest first, items `{account (unmasked), kind, text, at}` |
| C7 | 21 x `low_balance` for HG621000002 | 20 x 202, then 429 `{"error":"rate limited"}`; outbox length 20 |
| C8 | `fields.account:"X"` override attempt | ignored, text uses `****0003` |
| C9 | `GET /health` | 404 (accepted difference after: 200) |
| C10 | `GET /notify` | 404 |

  Still to add: outbox read cap (55 posts, `GET` returns 50), `TTL notify:rate:<acct>` = 3600 and outbox keys with no TTL (`redis-cli`), 400s do not consume rate budget, malformed JSON body status, stdout line `queued <kind> for ****NNNN`, Redis down -> 503 `store unavailable`.
- **Unit tests to `test` stage**: `npm test` (`test/templates.test.js`, 4 assertions; passes) runs as `RUN npm test` in the `test` stage. Add an in-process variant of C1-C10 using a Redis started inside the test stage or a small fake, so `docker build --target test` covers the HTTP contract without the stand-in.
- **Parity report rows**: one per case C1-C10 plus: rate-limit semantics (per box -> global, accepted difference with reason), outbox location (two hosts -> one store, accepted difference), log destination (files -> stdout, accepted), process model (2 PM2 workers x 2 VMs -> 2 pods), memory at idle and after a 1-hour soak (before ~44 MB per worker), runtime and base image, `/health` (404 -> 200, accepted). A failed row stays failed.
- **Kind smoke paths** (`deploy/platform.yaml`): `/health` 200, `/outbox/HG611000001` 200, `/notify` 404. A POST round-trip (C1 then C6) is run by the characterization suite against the port-forward, since the pipeline smoke is GET-only.

## 6. Effort estimate

**M: 6-10 engineer-days**, one engineer.

| Work item | Days |
|---|---|
| Characterization suite (cases C1-C10 + remaining), run on stand-in, keep output | 1-1.5 |
| Code: env config, Redis auth/TLS, `/health`, SIGTERM, Node 20 + express 4.21 bump, lockfile | 1-1.5 |
| Dockerfile (`test` + runtime stage, digest pins, USER 10001), `.dockerignore` | 0.5 |
| `deploy/` (values, platform.yaml, values-ci, kind-deps Redis, kind-secrets) and green local `policy-check.sh` / `kind-verify.sh` | 0.5-1 |
| Managed Redis: request/provision (Terraform, outside this app), Secrets Manager entry, ExternalSecret, network access | 1.5-3 |
| Gateway contract and cut-over plan: how SMS/push gateways drain the outbox, single store vs two, draining notify-01/02 | 0.5-1.5 |
| Pipeline runs, Trivy findings, parity report | 1 |
| **Total** | **6-10** |

Assumptions: the platform team (or an existing module) can provide a managed Redis and an External Secrets store; the gateways read Redis directly and need only a new endpoint plus credentials, not code changes; no new Node base is required before the first run (Node 20 accepted for now); characterization tests do not uncover hidden behavior behind the 03:30 restart.

## 7. Verdict

**replatform.** The code is small, stateless apart from Redis, already logs to stdout, uses UTC timestamps and has no secrets, TLS or file I/O; every host tie is removed by configuration, a health endpoint, a Dockerfile and a chart values file, without changing the business logic. A rewrite buys nothing (46 lines of server code). Retain is not justified: the host is on an EOL OS and an EOL runtime, and nothing ties the service to the VM that a managed Redis cannot replace. I **agree** with the manifest's `expected: replatform`, but the manifest under-counts the work: it misses the missing `/health` (the first runtime-stage failure), root user, the 300M memory ceiling vs the 256Mi limit, and the per-host Redis state whose consolidation changes rate-limit and outbox behavior.

**Biggest blocker:** Redis is assumed on 127.0.0.1:6379 with no password and holds per-host outbox and rate-limit state (`src/server.js:10`); meeting the standard needs a managed Redis with its password as a `secretEnv` ref, plus an agreed contract with the SMS/push gateways that drain the outbox.

## 8. Risks and open questions

- **Gateway contract (open).** `GET /outbox` only reads (`LRANGE 0..49`, `src/server.js:40`) and nothing in the app removes items, so the SMS/push gateways must pop `notify:outbox:*` from each box's Redis directly. Who owns them, how do they connect today (two Redis endpoints?), and can they move to one authenticated TLS endpoint at cut-over?
- **Unbounded outbox.** `LPUSH` with no `LTRIM`/`EXPIRE` (`src/server.js:31`); if the gateways fall behind, Redis grows without bound. Is that why the box restarts nightly, or why PM2 caps memory? Size the managed Redis and add an eviction/alert policy.
- **Durability.** Is the VM Redis persisted (RDB/AOF)? The stand-in runs `redis-server` with no config. Queued notifications must survive the cut-over; decide drain-then-switch vs dual-write.
- **Rate-limit semantics change** from per box to global; confirm with the business owner that 20/hour per account across the service is the intended rule (it is likely what was meant). A 429 still increments the counter (`src/server.js:26-29`), and `EXPIRE` is fire-and-forget only on the first hit; keep identical for parity, flag as a follow-up.
- **Node 20 is EOL** (2026-04-30) and is the only Node image in `base-images.yaml`; Trivy runs with `--ignore-unfixed`, so it may pass now and start failing later. Request a Node 22/24 LTS entry from the platform team.
- **Policy gap:** `policy/conftest/dockerfile.rego` checks only `FROM`; `COPY --from=<external image>` (as `vm/Dockerfile:3` does) bypasses BASE-01. Worth reporting to the platform team.
- **PII:** `GET /outbox/:account` returns the full account id and is unauthenticated (`src/server.js:30,39-43`); keep the service ClusterIP-only with no ingress and restrict the NetworkPolicy to the gateways' namespace.
- **Owner and cost center** for `deploy/values.yaml` are not recorded anywhere in the wave folder.
- **Standards location:** `ESTATE.md:3` says the standards are on `main`; they are only on `devin/1792540800-platform-standards` (c56cbe8). The app should pin that commit as `standards_ref` until it merges.
- **DeepWiki:** asked about notify-svc, `industries/banking/vmware-wave-1` and `platform/standards`; the index knows neither (it answered about the unrelated `services/notification-service`). This note relies on the code.

**What was run for this note:** `npm test` on Node v24.19.0 (pass, 4 assertions); the `notify-01` stand-in built and started (`docker compose -f vm/compose.yaml`, Docker Hub rate-limited the bases, pulled `node:12-bullseye` and `redis:6.2-bullseye` from `mirror.gcr.io` and built with `DOCKER_BUILDKIT=0`), cases C1-C10 above executed against http://localhost:8084, then the container removed. No cloud resources touched.
