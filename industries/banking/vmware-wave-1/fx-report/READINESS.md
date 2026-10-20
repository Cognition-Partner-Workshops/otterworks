# fx-report: wave-1 readiness

## 1. Summary

fx-report is the FX desk's morning page: a single Perl CGI script (`cgi-bin/fx-report.cgi`, 35 lines) and one module (`lib/FxReport/Rates.pm`, 35 lines) run by Apache 2.2 through `mod_cgi` on report-01 (RHEL 6, system Perl 5.10). It reads `rates-<day>.csv` and the previous calendar day's file from `/mnt/rates-out`, an NFS mount of rates-batch's output spool, and renders one HTML table (close, average mid, intraday range, day-on-day change per pair). Sign-in (`mod_authnz_ldap`, group `fx-desk`) and caching (`mod_expires`, one hour) live in the Apache config, not in the app. About a dozen users read it on weekday mornings. Nothing in `base-images.yaml` can run Perl or Apache, the sign-in and caching have to move out of web-server modules anyway, and the NFS input goes away once rates-batch moves to the cluster in this wave. The business logic is small enough that rewriting it as a stdlib Python service on the approved Python base costs less than getting a Perl/Apache image approved and hardening Apache to run read-only and non-root.

**Verdict: rewrite** (a small Python service on `python-3.12-slim`, same URL, same output, pinned by characterization tests against the VM stand-in).

## 2. Runtime and versions

| Item | On the VM (HOST.md) | In the VM stand-in (`vm/Dockerfile`, observed) | Proposed target |
|---|---|---|---|
| OS | RHEL 6 (end of maintenance Nov 2020) | Debian (from `docker.io/library/httpd:2.4`, unpinned) | Debian bookworm from the approved base |
| Language runtime | system Perl 5.10 | Perl 5.40.1 | Python 3.12 (see note) |
| Web server | Apache 2.2 (EOL, last release 2017) with `mod_cgi`, `mod_authnz_ldap`, `mod_expires` | Apache 2.4.69 with `mod_cgid`, no LDAP, no `mod_expires` | none: Python stdlib `http.server.ThreadingHTTPServer` on port 8080 behind ingress-nginx |
| Libraries | CGI.pm from OS packages (dropped from Perl core in 5.22), POSIX | CGI.pm 4.68 (`libcgi-pm-perl`) | Python stdlib only (`csv`, `html`, `datetime`, `zoneinfo`) |
| Tests | `t/rates.t`, Test::More, 3 assertions | n/a | `unittest`/pytest in the Dockerfile `test` stage |
| Build files | none: files are copied by hand (HOST.md:6) | n/a | multi-stage Dockerfile |

Base image: `python-3.12-slim` from `platform/standards/base-images.yaml` (`docker.io/library/python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1`) for both the `test` and final stages, as in `examples/sample-service/Dockerfile`. No approved image carries Perl or Apache httpd, so keeping the current code would need a new base image approved through a platform pull request first. Note on versions: the `modernization-target-standard` skill names Python 3.11, but the only approved Python image is 3.12 and the platform gate (BASE-01) wins; the code would stay 3.11-compatible (stdlib only, no 3.12-only syntax). See open question Q1.

## 3. Host ties

Line numbers checked with `grep -n` / `cat -n` on commit e42786c. Paths are relative to `industries/banking/vmware-wave-1/fx-report/`. "Manifest" says whether `complexity-manifest.json` lists the tie (its three conditions are `web-server-modules`, `shared-filesystem`, `eol-runtime`; the first is split into rows 1-3 here). Rows marked **NEW** are not in the manifest.

| # | Id | What the host gives the app | file:line | Platform rule it breaks | Manifest |
|---|---|---|---|---|---|
| 1 | cgi-runtime | Apache `mod_cgi` forks a Perl process per request; the app has no server of its own | `vm/fx-report.conf:2`, `vm/fx-report.conf:6-8`, `cgi-bin/fx-report.cgi:8` | BASE-01 (no approved Perl/httpd image), PROBE-01 (no long-running service to probe), SEC-02 (Apache writes its pid file and cgid socket under its own tree; observed in the stand-in in `/usr/local/apache2/logs`) | yes (web-server-modules) |
| 2 | ldap-signin | Sign-in and authorization: `mod_authnz_ldap`, Basic auth, `Require ldap-group cn=fx-desk` | `vm/fx-report.conf:3`, `vm/fx-report.conf:9-13` | No direct rule; the chart's ingress (`helm/app/templates/ingress.yaml`) has no auth hook, and NET-01 puts the app behind the shared ingress-nginx, so sign-in must move to the ingress or into the app | yes (web-server-modules) |
| 3 | expires-cache | One-hour browser caching via `mod_expires`; the script itself sends only `Content-Type` | `vm/fx-report.conf:4`, `vm/fx-report.conf:14-15`, `cgi-bin/fx-report.cgi:21` | No rule; behavior to reproduce in the app (`Cache-Control: max-age=3600`) | yes (web-server-modules) |
| 4 | nfs-input | Input spool is the NFS export of rates-01's `/var/spool/rates/out`, read by absolute path | `cgi-bin/fx-report.cgi:12`, `cgi-bin/fx-report.cgi:18-19`, `lib/FxReport/Rates.pm:9`, `HOST.md:8` | Config from env/mounted files (path is hard-coded); the chart only mounts `emptyDir` (`writablePaths`) and a ConfigMap (`configFiles`), no shared volume, so the handoff needs a new store | yes (shared-filesystem) |
| 5 | eol-runtime | RHEL 6, Apache 2.2, system Perl 5.10 | `HOST.md:5`, `cgi-bin/fx-report.cgi:1` (`#!/usr/bin/perl`) | BASE-01 | yes (eol-runtime) |
| 6 | os-cgi-pm | CGI.pm from the OS packages (no longer in Perl core since 5.22, no cpanfile) | `HOST.md:5`, `cgi-bin/fx-report.cgi:8` | BASE-01 (dependency only exists on the host image) | **NEW** |
| 7 | absolute-lib-path | Module path pinned to the host install location | `cgi-bin/fx-report.cgi:7` (`use lib '/var/www/fx-report/lib'`) | Config from env/mounted files; no image layout | **NEW** |
| 8 | hand-install | Deployed by copying files by hand; no build, no package, no version | `HOST.md:6` | Pipeline: no `Dockerfile`, no `test` stage, no `deploy/` | **NEW** |
| 9 | host-timezone | Default business date is "yesterday" in the host's local zone; the stand-in passes `TZ` through Apache | `cgi-bin/fx-report.cgi:13` (`localtime(time - 86400)`), `vm/Dockerfile:7` (`PassEnv TZ`) | Config from env (zone must be an explicit setting; containers run UTC) | **NEW** |
| 10 | remote-user | User name shown on the page comes from `REMOTE_USER`, set by the LDAP module | `cgi-bin/fx-report.cgi:23` | No rule; identity must come from the new auth layer (header from the ingress auth proxy or an in-app session) | **NEW** |
| 11 | ldap-host-plaintext | Directory reached by hostname `ldap.bank.internal` over plain `ldap://`; Basic credentials with no TLS configured on the vhost | `vm/fx-report.conf:9`, `vm/fx-report.conf:12` | NET-01 / ingress TLS (`ingress.tls: true` default); no in-cluster DNS for `bank.internal` assumed | **NEW** |
| 12 | no-health | Only `/fx/` is mapped; `/health` answers 404 (observed in the stand-in) | `vm/fx-report.conf:6` | PROBE-01, and the chart wires `/health` to both probes, so pods never become ready | **NEW** |
| 13 | port-80-root | Served on port 80 by an Apache master running as root (stand-in base `httpd:2.4`, `id` = uid 0); URL path `/fx/fx-report.cgi` | `HOST.md:9`, `vm/Dockerfile:4`, `vm/fx-report.conf:6` | BASE-02, SEC-01 (uid 10001 cannot bind :80); chart default `containerPort: 8080` | **NEW** |
| 14 | apache-error-log | Script warnings go to Apache's `error_log` (observed: `Use of uninitialized value $m ... line 16` for `day=bad`); access log is Apache's. On RHEL 6 these are files under `/var/log/httpd` (default layout, not in the repo, inferred) | `cgi-bin/fx-report.cgi:16` | Logs on stdout/stderr, no log file in the container | **NEW** |

14 host ties, 9 of them not in the manifest. Not present (checked): no credential in the app or its config (LDAP bind is anonymous, no `AuthLDAPBindDN`), no session state, no cron, no database, no outbound calls other than LDAP. SECRET-01..04 would pass as-is.

## 4. Changes to meet platform/standards

Ordered; each step lands in the same pull request unless stated.

1. **Characterization tests first** (section 5) against the stand-in, golden outputs committed under `tests/golden/`.
2. **Rewrite** `FxReport::Rates` and the CGI as one Python module (`app/fxreport.py`, stdlib only): `read_day(path)`, `moves(today, prev)`, `render(day, user, rows)`, and a `ThreadingHTTPServer` handler. Preserve exactly: route `/fx/fx-report.cgi?day=yyyy-mm-dd` (bookmarks), date validation (including Perl's `$` accepting a trailing newline), previous *calendar* day lookup with month/year rollover, pairs sorted, `close` and `avg` echoed as the CSV strings (no float re-formatting, e.g. `0.949310`), range `%.5f`, change `%+.3f%%` or `n/a`, the "No rates file for this day yet." branch, HTTP 200 for an invalid date. Add `GET /health` returning 200 when the input source is reachable (directory listable / bucket head succeeds).
3. **Configuration from env**: `RATES_DIR` (replaces `/mnt/rates-out`, hard-coded at `cgi-bin/fx-report.cgi:12`), `RATES_SOURCE` if S3 is chosen (`s3://<bucket>/<prefix>`), `REPORT_TZ` (replaces host `localtime`, `cgi-bin/fx-report.cgi:13`), `USER_HEADER` (default `X-Auth-Request-User`, replaces `REMOTE_USER`), `CACHE_SECONDS=3600` (replaces `mod_expires`), `PORT=8080`.
4. **Input handoff with rates-batch** (needs a decision with the rates-batch reviewer and the platform team, Q2): preferred is rates-batch's CronJob writing `rates-<day>.csv` to an S3 prefix and fx-report reading it through IRSA (no secret, nothing writable in the pod). If S3 is chosen, the reader needs an S3 client; stdlib-only can be kept only with a mounted RWX volume, which the chart does not support today. For kind, `deploy/values-ci.yaml` sets `RATES_DIR=/etc/app` and puts the three seed-day files in `configFiles` (rendered as a read-only ConfigMap mount), so smoke runs without any dependency.
5. **Sign-in**: move LDAP Basic auth to the ingress (ingress-nginx `auth-url`/`auth-signin` to the bank's SSO proxy, group `fx-desk`), app reads the user from `USER_HEADER`. The platform chart's ingress template only sets the cert-manager annotation, so this needs either an `ingress.annotations` value in `helm/app` (platform pull request) or an in-app OIDC/LDAP check with its client secret delivered through `secretEnv` (Q3). Until decided, the app must not be exposed through ingress (`ingress.enabled: false`, the chart default).
6. **Dockerfile** at the app root, two stages, both `FROM docker.io/library/python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1`: first stage `AS test` copies the app and tests and runs `python -m unittest -v` (so `docker build --target test` is the unit test step); final stage copies only the app, `ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1` (no credential names in `ENV`/`ARG`, SECRET-04), `USER 10001`, `EXPOSE 8080`, `CMD ["python", "fxreport.py"]`.
7. **Logging**: access lines and warnings to stdout/stderr through `logging`; no file handlers.
8. **Read-only root fs**: the app writes nothing; keep the chart default `writablePaths: [/tmp]` as the only `emptyDir`.
9. **Resources**: chart defaults (requests 100m/128Mi, limits 500m/256Mi) are enough for a dozen users; no override.
10. **`deploy/values.yaml`**: `app: fx-report`, `owner: <fx-desk application team>`, `costCenter: <FX desk code>` (Q4), `workload: web` (Deployment, not CronJob: it serves requests), `containerPort: 8080`, `env` from step 3, `secretEnv` only if step 5 lands in-app.
11. **`deploy/platform.yaml`**: `app: fx-report`; smoke `GET /health` 200, `GET /fx/fx-report.cgi?day=2026-10-16` 200, `GET /fx/fx-report.cgi?day=2026-10-20` 200 (missing-day branch).
12. **Decommission**: after parity sign-off and one week of side-by-side, retire report-01's vhost and the NFS export (with rates-batch).

**What the first pipeline run would fail today** (pointing `app_dir` at the app as it is): the "Unit tests (Dockerfile test stage)" step fails at once because there is no `Dockerfile` at the app root, the build step fails with it, and the policy gate and kind stages are skipped (they need a successful build). If someone used `vm/Dockerfile` instead: no `test` stage (unit step fails), BASE-01 (`httpd:2.4` is not approved and not digest-pinned), BASE-02 (no `USER`), `helm template` errors on the missing `app`/`owner`/`costCenter` (LABEL-01) with no `deploy/values.yaml`, and at runtime SEC-02/SEC-01 (Apache cannot write its pid/socket on a read-only root fs and uid 10001 cannot bind :80) and PROBE-01 (`/health` 404, readiness never passes, smoke fails). REG-01/REG-02 and SECRET-01..04 would pass. After the changes above, the expected first-run risk is only the kind smoke if the fixture files are not mounted.

## 5. Test strategy

**Characterization tests (before any change).** A small Python script `tests/characterize.py` takes a base URL and records status, `Content-Type`, `Cache-Control`/`Expires` and the HTML body for each case, written to `tests/golden/*.html` and `golden.json`. Run against the stand-in: `make vm-up` in `industries/banking/vmware-wave-1` (rates-batch fills the shared `rates-out` volume for 2026-10-14..16 from `data/rates/in/`), base URL `http://localhost:8086/fx/fx-report.cgi` (ESTATE.md, HOST.md:12). Cases:

- `day=2026-10-16` and `day=2026-10-15` (full table with changes), `day=2026-10-14` (first seed day, all `n/a`)
- `day=2026-10-20` (no file: "No rates file for this day yet.")
- `day=bad` (empty business date, 200, warnings on stderr), `day=2026-10-16%0A` (trailing newline passes the regex)
- no `day` with the container `TZ` pinned, compared against `date -d yesterday` in that zone
- month/year rollover of the previous day (2026-11-01 -> 2026-10-31, 2026-03-01 -> 2026-02-28) through a fixture spool, since the seed data only has three consecutive weekdays
- Monday behavior: previous day is Sunday, so change is `n/a` unless a weekend file exists (pinned, not "fixed")

The same script runs unchanged against the new service (`kubectl port-forward` in kind, or `docker run` locally) and compares.

**Unit tests.** `t/rates.t` (3 assertions on `moves`) becomes `app/test_fxreport.py` with the same three cases plus `read_day` on the 2026-10-16 seed output and the formatting rules; it runs in the Dockerfile `test` stage (`python -m unittest -v`), which is the pipeline's unit step.

**Parity report rows** (before = stand-in, after = new service, same seed files):

| Check | Comparison |
|---|---|
| Table rows for 2026-10-14, -15, -16 | byte-identical `<tr>` rows (pair, close, avg, range, change) |
| Missing day / invalid day / trailing newline | same status and message |
| Default day with `TZ` pinned | same business date |
| HTML boilerplate | accepted difference: CGI.pm XHTML doctype/head vs plain HTML5 head, body content identical |
| Caching | accepted difference: stand-in sends no `Expires` (no `mod_expires`); new service sends `Cache-Control: max-age=3600`, matching the production vhost |
| User shown | stand-in `unknown`; new service shows the `USER_HEADER` value (and `unknown` without it) |
| `/health` | before 404, after 200 (new) |

**Kind smoke** (`deploy/platform.yaml`): `/health`, `?day=2026-10-16`, `?day=2026-10-20`, all 200, with the seed-day rates files from `deploy/values-ci.yaml` `configFiles`.

**What I ran for this note.** `prove -v t/` on the VM's Perl 5.34: 3/3 pass. `make vm-up` could not build here: Docker Hub returned 429 for the stand-in base images (worked around by pulling through `mirror.gcr.io`) and the rates-batch Maven build could not resolve plugins (no `MAVEN_MIRROR`). Instead I generated the spool with the real rates-batch code (`java rates-batch/src/main/java/com/bank/rates/RatesJob.java data/rates/in <out> <day>` for 2026-10-14..16, 5 pairs each), built the fx-report stand-in image with `docker compose build report-01`, and ran it with `docker run -v <out>:/mnt/rates-out:ro -p 8086:80`. Observed: `?day=2026-10-16` 200 with five rows (e.g. `EURUSD 1.087220 1.088876 0.00845 -0.260%`), `?day=2026-10-14` 200 all `n/a`, `?day=2026-10-20` and `?day=bad` 200 "No rates file", no `day` -> 2026-10-19 (UTC), `/health` 404, Apache running as uid 0 with a pid file and cgid socket under `/usr/local/apache2/logs`, Perl 5.40.1 and CGI.pm 4.68 in the stand-in. The container was removed afterwards.

## 6. Effort estimate

**M: 6-10 engineer-days.**

| Work item | Days |
|---|---|
| Characterization script and golden outputs against the stand-in, plus one capture from report-01 itself | 1 - 1.5 |
| Python rewrite (reader, moves, rendering, `/health`, env config, stdout logging) | 1 - 1.5 |
| Port `t/rates.t` and add formatting/date-edge unit tests; Dockerfile with `test` stage | 0.5 - 1 |
| `deploy/values.yaml`, `values-ci.yaml` fixtures, `platform.yaml`, pipeline green on kind | 1 - 1.5 |
| Input handoff with rates-batch (S3 prefix and IRSA, or shared volume), reader for it | 1 - 2 |
| Sign-in replacement (ingress auth to SSO with the `fx-desk` group, or in-app) | 1 - 2 |
| Parity report, side-by-side week with the desk, retire report-01 vhost | 0.5 - 0.5 |
| **Total** | **6 - 10** |

Assumptions: the platform team accepts Python 3.12 (or adds a 3.11 image) and either an ingress auth annotation or an in-app sign-in; the rates-batch replatform defines the output store in the same wave; no other consumers of the page beyond the desk's browsers; the bank's SSO already exposes the `fx-desk` group.

## 7. Verdict

**rewrite.** Reasons, from the code:

- Nothing approved can run it: `base-images.yaml` has Tomcat, Temurin, Python and Node only, so keeping Perl + Apache means a new base image through the platform's change process plus hardening Apache for a read-only root fs, non-root and port 8080, to keep 70 lines of logic.
- The parts that are not business logic (sign-in, caching, process model, logging) are all Apache features and must be replaced whatever the language.
- The logic is small, pure and already covered by a unit test; a stdlib Python port with golden-output tests is low risk and lands on the approved base with no third-party dependencies.
- `retain` was considered: a dozen users could stay on report-01, but RHEL 6 and Apache 2.2 are out of support, and once rates-batch leaves rates-01 the NFS export that feeds the page disappears, so retaining fx-report would mean keeping a cross-environment file handoff alive for one page.
- `replatform` (same Perl code in a container) fails BASE-01 with no approved image and is the most work for the least gain.

The manifest's `expected` is `retain-or-rewrite`; this verdict picks the `rewrite` branch, so I agree with it.

## 8. Risks and open questions

Risks:

- **Stand-in is not production.** The stand-in runs Perl 5.40, CGI.pm 4.68 and Apache 2.4 without LDAP or `mod_expires`; report-01 runs Perl 5.10 and Apache 2.2. Golden HTML from the stand-in may differ from production in boilerplate; capture at least one page from report-01 before cutover.
- **Calendar vs business previous day.** The change column compares with the previous calendar day (`cgi-bin/fx-report.cgi:16`), so Monday's report shows `n/a` unless a weekend file exists. The rewrite keeps this; changing it is a desk decision, not part of the move.
- **Timezone coupling with rates-batch.** Both apps derive "yesterday" from the host zone; if rates-batch's CronJob runs in `Etc/UTC` (chart default) and fx-report uses a local zone, the default page can point at a day that has not been produced yet.
- **Positional CSV contract.** `lib/FxReport/Rates.pm:15` reads columns by position and ignores the header (`pair,open,high,low,close,avg_mid,ticks`); any column change in rates-batch breaks the page silently. Pin the header in both apps' tests.
- **Division by zero** if a previous close is `0` (`lib/FxReport/Rates.pm:28`); the CGI would die with a 500. Keep the same behavior or agree a change explicitly.
- **Close and average are not HTML-escaped** (`cgi-bin/fx-report.cgi:31`); input is trusted batch output, but the rewrite should escape every cell (accepted difference only if a value contains markup, which seed data does not).
- **Docker Hub rate limits** hit this environment; the pipeline pulls by digest from Docker Hub too.

Open questions:

- Q1: Python 3.12 (only approved Python image) vs the skill's Python 3.11 target: accept 3.12, or will the platform team add a 3.11 digest?
- Q2: Where does rates-batch's output live after its replatform (S3 prefix with IRSA, or a shared RWX volume the chart would need to support)? fx-report's reader follows that decision.
- Q3: Sign-in: will `helm/app` gain an `ingress.annotations` value for ingress-nginx external auth, or should the app do OIDC/LDAP itself (adds a client secret via `secretEnv`)? Is there an SSO proxy that exposes the `fx-desk` group?
- Q4: `owner` and `costCenter` values for `deploy/values.yaml`.
- Q5: Which zone is "local time" on report-01 (for `REPORT_TZ`)?
- DeepWiki: asked about fx-report, `industries/banking/vmware-wave-1` and the platform standards (base images, chart, conftest/Kyverno); its index predates this branch and it knew nothing about fx-report, rates-batch or `platform/standards`, answering only about the existing `infrastructure/helm` charts' health probes. This note relies on the code.
- ESTATE.md says the standards live on `main`; at the time of writing they exist only on `devin/1792540800-platform-standards` (c56cbe8). The pipeline `standards_ref` should pin whichever commit lands.
