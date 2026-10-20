# statements-web: wave-1 readiness

Reviewed against `industries/banking/vmware-wave-1` at commit `e42786c9e757919151d390c79429b6f899bfadac` and the platform standard `platform/standards/` at commit `c56cbe8f6f4c55242cdece90701e8754566fcc01` (branch `devin/1792540800-platform-standards`; it is not on `main` yet, although ESTATE.md says it is). File references are relative to `industries/banking/vmware-wave-1/statements-web/` unless they start with `industries/` or `platform/`.

## 1. Summary

statements-web is a small Java 8 WAR (five classes, about 230 lines, two servlets) on Tomcat 8.5. It renders the account list and one account's statement lines from PostgreSQL. The business logic is plain JDBC and string-built HTML with nothing tied to the platform. Everything that ties it to the VM is outside that logic: a JNDI datasource with a literal password and hostname in Tomcat's `context.xml`, settings read from `/opt/app/conf`, log4j 1.x writing a daily file under `/var/log`, last-viewed state in the HTTP session (the hardware load balancer pins users with a cookie), no health endpoint, a root-run Tomcat that writes to its own install tree, and a set of EOL parts (Java 8, Tomcat 8.5, RHEL 7, log4j 1.2.17, pgjdbc 42.2.27 with a fixed CRITICAL CVE). I found 20 host ties. The manifest lists 5 of them. Each one can be fixed with configuration or a small code change on an approved Tomcat 9 base, and the code does not need a rewrite. The hardest part is the datasource and credential work, because it needs a Secrets Manager entry and a least-privilege database role. The open security question in section 8 is that the app does no authentication or authorization.

**Verdict: replatform** (agrees with the manifest's `expected: replatform`). Effort **M: 7-10 engineer-days**.

## 2. Runtime and versions

| Item | Today (source) | Proposed target |
|---|---|---|
| OS | RHEL 7 (HOST.md:5), EOL. The stand-in is the Debian-based `tomcat:8.5-jre8` image (vm/Dockerfile:13) | Ubuntu 22.04 (jammy), from the approved base image |
| Java | Oracle JRE 8u202 from `/usr/java/jre1.8.0_202` (HOST.md:5). Source/target 1.8 (pom.xml:12-13). The stand-in has OpenJDK 1.8.0_402 | **Java 17 (Temurin)**: compile with `--release 17`. The skill's target is Java 21, but `base-images.yaml` has no Java 21 image yet. See note below |
| Servlet container | Tomcat 8.5 under `/opt/tomcat` (HOST.md:5). The stand-in runs Apache Tomcat 8.5.100. Tomcat 8.5 is EOL | **Tomcat 9.0**, approved base `tomcat-9-jre17`: `docker.io/library/tomcat:9.0-jre17-temurin-jammy@sha256:729c7e1c48be985cdfc1fac9f50f1bcb0391ae911479a5b21574f2820e805845` |
| Servlet API | `javax.servlet-api` 3.1.0, provided (pom.xml:18-23). `web.xml` version 3.1 (WEB-INF/web.xml:2-4) | `javax.servlet-api` 4.0.1, provided. Tomcat 9 is still `javax.*`, so no jakarta migration is needed |
| Logging | log4j 1.2.17 (pom.xml:24-28), EOL with known CVEs | log4j 2.x current patch, with `log4j-1.2-api` as a bridge so the `org.apache.log4j.Logger` calls do not change, and a console appender |
| JDBC driver | `org.postgresql:postgresql:42.2.27.jre7`, copied into Tomcat `lib/` (vm/Dockerfile:10-11,14; HOST.md:10) | `org.postgresql:postgresql` 42.7.x current patch, still in `$CATALINA_HOME/lib` because the JNDI pool needs it there |
| Connection pool | Tomcat DBCP2 through the `<Resource>` (vm/conf/context.xml:5-9), maxTotal 20 per VM | Keep Tomcat DBCP2. Lower `maxTotal` to about 5 per pod |
| Build | Maven 3.9 on Temurin 8 (vm/Dockerfile:3, `maven-3.9-jdk8`, approved for build). maven-war-plugin 3.4.0 (pom.xml:40-44) | Approved build image `maven-3.9-jdk17`: `docker.io/library/maven:3.9-eclipse-temurin-17@sha256:1a352420f7aba21f5ad08df31bab55f74c013fb491f1ae8ab1dd7ff9ed698584`, as the `test` stage |
| Tests | JUnit 4.13.2 (pom.xml:29-34), 2 tests in HtmlTest.java | JUnit 4.13.2 kept (or JUnit 5), plus HTTP characterization tests (section 5) |
| Database | PostgreSQL 16 in the stand-in (`industries/banking/vmware-wave-1/vm/compose.yaml:6`). The production DB VM version is not stated | PostgreSQL 15 per the modernization standard. The SQL is ANSI and has no version-specific features |

**Java version note.** The org standard targets Java 21 Temurin and Spring Boot 3.3.x. The platform gate (BASE-01) only allows the images in `base-images.yaml`. For a WAR, the newest is `tomcat-9-jre17`, and there is no Tomcat 10.1 or JRE 21 image. Two options:
- Replatform on Java 17 / Tomcat 9 now, which passes the gate today.
- Have the platform team add a `tomcat:10.1-jre21-temurin` digest first. That also brings a `javax`→`jakarta` rename, which is mechanical for five classes.

Spring Boot 3.3 would be a rewrite of a two-servlet app and is not justified. **Decision for the wave lead.** This note assumes Java 17 / Tomcat 9.

## 3. Host ties

The "In manifest" column shows whether `complexity-manifest.json` lists the tie. **NEW** marks the ones it does not list. Line numbers were checked with `nl -ba`/`grep -n` at commit e42786c.

| Id | What the host gives the app | file:line | Platform rule broken | In manifest |
|---|---|---|---|---|
| T01 host-path | Settings file at the absolute path `/opt/app/conf/statements.properties`. The app throws `IllegalStateException` if it is missing. The stand-in bakes the file into the image | src/main/java/com/bank/statements/AppConfig.java:9, :18-21; vm/opt-app-conf/statements.properties:1-3; vm/Dockerfile:16; HOST.md:8 | "Configuration from environment variables and mounted files" (README, application requirements). The chart mounts files at `/etc/app` | yes |
| T02 container-datasource | Container-managed JNDI `jdbc/StatementsDB`, defined in Tomcat's `conf/context.xml` and looked up by name | src/main/java/com/bank/statements/StatementDao.java:20; src/main/webapp/WEB-INF/web.xml:25-29; vm/conf/context.xml:5-9; HOST.md:7 | Configuration from env/mounted files. The config lives in the server install, not the app | yes |
| T03 credential literal | DB user and password written in plain text in `context.xml` and baked into the image. The stand-in DB uses the same literal | vm/conf/context.xml:8; vm/Dockerfile:15; `industries/banking/vmware-wave-1/vm/compose.yaml:9-10` | BASE-02 ("bakes in no credential"), SECRET-01..04 intent, Trivy `platform-hardcoded-db-password` (HIGH) | partly: inside container-datasource's detail, not its own condition |
| T04 DB hostname | Database reached by the host name `wave1-db` on a fixed port in a fixed JDBC URL | vm/conf/context.xml:7; HOST.md:7 | Configuration from env | **NEW** |
| T05 over-privileged DB role | `statements_app` (password "...-Ro!") is the database owner and a **superuser** in the stand-in (`rolsuper = t` checked with psql). `db-roles.sql` creates a read-only role only for branch-locator | `industries/banking/vmware-wave-1/vm/compose.yaml:9`; `industries/banking/vmware-wave-1/vm/db-roles.sql:2-3` | Secret handling and least privilege (secrets via `secretEnv` from Secrets Manager). No gate rule checks this, but it must not move to the cluster | **NEW** |
| T06 file-logging | log4j 1.x `DailyRollingFileAppender` to `/var/log/statements/statements.log`, root logger file-only | src/main/resources/log4j.properties:1-4; HOST.md:9 | "Logs on stdout and stderr", SEC-02 (read-only root fs) | yes |
| T07 Tomcat's own log files | Tomcat writes `catalina.<date>.log`, `localhost.<date>.log`, `localhost_access_log.<date>.txt`, etc. under `$CATALINA_HOME/logs`. Seen in the running stand-in. This comes from the base image's `conf/logging.properties` and `server.xml` | vm/Dockerfile:13 (base image config, not in the repo) | Logs on stdout, SEC-02 | **NEW** |
| T08 log shipping | A nightly rsync copies the log file to the log server | HOST.md:9 | Logs on stdout, collected by the cluster | **NEW** |
| T09 session-affinity | "Last viewed" account kept in `HttpSession`. Every `/accounts` hit creates a session (`getSession(true)`), so every user gets a `JSESSIONID`. `<distributable/>` is declared, but no session replication is configured, so state survives only because the hardware LB pins users by cookie | src/main/java/com/bank/statements/StatementServlet.java:28 (write); src/main/java/com/bank/statements/AccountsServlet.java:23 (read, creates the session); src/main/java/com/bank/statements/Html.java:28-31 (render); src/main/webapp/WEB-INF/web.xml:30; HOST.md:3 | No rule ID covers it. The chart's ingress template (`helm/app/templates/ingress.yaml`) cannot set affinity annotations, so with 2 replicas behind ingress-nginx (NET-01) the state is lost | yes (StatementServlet only). AccountsServlet:23 and web.xml:30 are **NEW** |
| T10 missing-probe | No `/health`. Only `/accounts` and `/statement` are mapped. The stand-in returns 404 for both `/health` and `/statements/health` | src/main/webapp/WEB-INF/web.xml:6-21 | PROBE-01. "A `/health` endpoint that answers 200" (README) | yes |
| T11 context path | The WAR deploys as `statements.war`, so every URL sits under `/statements`. A `/health` endpoint inside it would be `/statements/health`, not the `/health` the chart probes and the smoke paths call | pom.xml:38; HOST.md:6, :11 | PROBE-01 / chart default `probes.path: /health` | **NEW** |
| T12 EOL Java 8 / Oracle JRE | Oracle JRE 8u202 is the last free-licence Oracle 8 build. The code compiles at 1.8 | pom.xml:12-13; HOST.md:5 | Org target (Java 21/17). Not a gate rule by itself (`tomcat-9-jre8` is approved) | **NEW** |
| T13 EOL Tomcat 8.5 / RHEL 7, unapproved base | Tomcat 8.5 (EOL) on RHEL 7 (EOL). The stand-in runtime base `tomcat:8.5-jre8` is not in `base-images.yaml` | vm/Dockerfile:13; HOST.md:5 | BASE-01 | **NEW** |
| T14 EOL log4j 1.2.17 | log4j 1.x is EOL and has CVEs with no fix in 1.x (for example CVE-2019-17571, CVE-2022-23305) | pom.xml:24-28 | Trivy image scan. With `--ignore-unfixed`, unfixed 1.x CVEs may be suppressed, but the library has to go anyway | **NEW** |
| T15 JDBC driver dropped into Tomcat lib | The driver is hand-copied into the server's `lib/`, outside the WAR. Version 42.2.27.jre7 has CVE-2024-1597 (CRITICAL, fixed in 42.2.28) | vm/Dockerfile:10-11, :14; HOST.md:10 | Trivy `--severity CRITICAL --ignore-unfixed --exit-code 1`: this one has a fix, so the step **fails** | **NEW** |
| T16 runs as root | The stand-in has no `USER` (vm/Dockerfile:13-19). The comment says it runs as root (vm/Dockerfile:1-2). `id` in the container shows uid 0 | vm/Dockerfile:1-2, :13-19 | BASE-02, SEC-01 | **NEW** |
| T17 writable install tree | Tomcat expands the WAR into `webapps/statements/` (seen in the stand-in) and writes `work/`, `temp/`, `logs/`. The image creates `/var/log/statements` owned by root | vm/Dockerfile:17-18 | SEC-02 (read-only root fs; writable paths must be `emptyDir`) | **NEW** |
| T18 manual deploy and systemd | The WAR is copied by hand, then `systemctl restart tomcat`. systemd is the process manager | HOST.md:6 | "nothing reaches the cluster any other way" than the pipeline. A Deployment replaces systemd | **NEW** |
| T19 two VMs behind a hardware LB | Two fixed hosts with a hardware load balancer (cookie pinning, and TLS presumably terminated there; the app has no TLS connector) | HOST.md:1, :3 | NET-01 (ClusterIP behind the shared ingress-nginx; TLS by cert-manager on the ingress) | **NEW** (only the pinning is in the manifest) |
| T20 host timezone | Statement dates come from `ResultSet.getDate` and print through `java.sql.Date.toString()`, both using the JVM default zone (the host's zone on RHEL, not stated in HOST.md). The stand-in and the chart run UTC. For a `DATE` column this should print the same calendar day, but it is unverified against production | src/main/java/com/bank/statements/StatementDao.java:51; src/main/java/com/bank/statements/Html.java:47 | No gate rule. A parity check is needed (section 5) | **NEW** |

Checked and not present: cron jobs, NFS mounts, `/etc/hosts` entries, web-server modules, local TLS keystores, LDAP, and outbound calls to other wave apps. statements-web reads only `accounts` and `statement_lines` from the shared `bankwave` DB (`industries/banking/vmware-wave-1/data/seed.sql:3-4`). No other wave app calls it. notify-svc has a `statement_ready` template but no call into statements-web. The container port is 8080 (vm/Dockerfile:19), which matches the chart's default `containerPort: 8080`.

## 4. Changes to meet platform/standards

In order. None of this is done here: this note is assessment only.

1. **Characterization tests first** (section 5), recorded against the stand-in before any change.
2. **Build upgrades**, in pom.xml:
   - `maven.compiler.release=17`
   - `javax.servlet-api` 4.0.1 provided
   - replace `log4j:log4j:1.2.17` with `org.apache.logging.log4j:log4j-core` + `log4j-1.2-api` (no code change to the logger calls)
   - add `org.postgresql:postgresql` 42.7.x as a `provided`/copied dependency for `$CATALINA_HOME/lib`
3. **Dockerfile at the app root** (the platform reads `$APP_DIR/Dockerfile`):
   - Stage 1: `FROM docker.io/library/maven:3.9-eclipse-temurin-17@sha256:1a35…8584 AS test`. It runs `mvn -B package`, which runs the JUnit tests (it is the `docker build --target test` step), and copies the pgjdbc jar.
   - Final stage: `FROM docker.io/library/tomcat:9.0-jre17-temurin-jammy@sha256:729c…5845`.
   - Remove the default webapps and **pre-explode** the WAR into `webapps/ROOT/`. In `server.xml`, set `unpackWARs="false" autoDeploy="false"`.
   - Copy the driver into `lib/`.
   - Copy a `context.xml` that has **no values**, only placeholders (see 4).
   - Copy a `logging.properties` with only `java.util.logging.ConsoleHandler`.
   - Remove the `AccessLogValve`, or point it at stdout.
   - `ENV CATALINA_OPTS` with the property source and the memory flags. No credential names in any `ENV`/`ARG`, so SECRET-04 holds.
   - `USER 10001:10001`, `EXPOSE 8080`.
4. **Datasource from env**:
   - Keep JNDI so `StatementDao` does not change. `context.xml` reads `url="${DB_URL}" username="${DB_USER}" password="${DB_PASSWORD}"`, resolved by Tomcat's `org.apache.tomcat.util.digester.EnvironmentPropertySource` (set via `-Dorg.apache.tomcat.util.digester.PROPERTY_SOURCE=…`; check it on the pinned 9.0 build).
   - Fallback: build the DataSource in a `ServletContextListener` from env.
   - `DB_URL` goes in `env`.
   - `DB_USER`/`DB_PASSWORD` go in **`secretEnv`**, pointing at a Secret (for example `statements-web-db`) that External Secrets fills from AWS Secrets Manager.
   - Create a **new read-only role** with `GRANT SELECT ON accounts, statement_lines` instead of reusing the superuser (T05).
   - Reduce `maxTotal`.
5. **Settings from env/mounted file**:
   - `AppConfig` reads `STATEMENTS_CONFIG` (default `/etc/app/statements.properties`, the chart's `configMountPath`). Supply `bank.name` and `statement.page.size` through `configFiles` in `deploy/values.yaml`.
   - Alternatively, take `BANK_NAME`/`STATEMENT_PAGE_SIZE` from env.
   - The 3-line properties file has no secret, so SECRET-03 passes.
6. **Logging to stdout**:
   - Replace log4j.properties lines 1-4 with a log4j2 `Console` appender that keeps the same `%d{ISO8601} %-5p [%t] %c - %m%n` pattern.
   - Tomcat's JUL logs go to the console as well (T07).
   - The nightly rsync (T08) is retired. Cluster log collection takes over.
7. **Session state removed**:
   - Replace `HttpSession` `lastAccount` with a small cookie: `lastAccount`, `Path=/statements`, `HttpOnly`, `Secure`, `SameSite=Lax`, validated with the same `[A-Z0-9]{8,20}` regex. Write it in StatementServlet.java:28 and read it in AccountsServlet.java:23.
   - Stop calling `getSession(true)`.
   - Remove `<distributable/>` (web.xml:30) or leave it inert.
   - The app is then stateless, so `replicas: 2` (matching the two VMs) needs no affinity. The hardware LB cookie pinning (T09/T19) is dropped.
   - Alternative: product agrees to drop "Last viewed".
8. **`/health` and the URL layout**:
   - Deploy as ROOT and map the servlets at `/statements/accounts` and `/statements/statement`. The public URLs stay the same (HOST.md:11), and the relative links in Html.java keep working.
   - Add a `HealthServlet` at `/health` that returns 200 when the datasource is bound and `SELECT 1` succeeds within a short timeout. The chart wires the same path to readiness and liveness, so see risk R4.
   - Map `/statements/` to the accounts page to keep the welcome behaviour.
   - Chart defaults (`probes.path: /health`, port `http`) then work unchanged.
9. **Read-only root fs**: `writablePaths` set to `/tmp`, `/usr/local/tomcat/work` and `/usr/local/tomcat/temp`. Also `/usr/local/tomcat/logs` if Tomcat still insists on the directory. Nothing else is written.
10. **Resources within 500m/256Mi**:
    - requests `cpu: 250m, memory: 256Mi`, limits `cpu: 500m, memory: 256Mi`.
    - JVM `-XX:MaxRAMPercentage=60 -XX:+UseSerialGC -Xss512k`.
    - Measure with the characterization run under load. Tomcat + JRE 17 fits in 256Mi, but with little headroom.
11. **`deploy/values.yaml`**:
    - `app: statements-web`, `owner: <team>`, `costCenter: <code>` (LABEL-01; owner team and cost centre to be supplied)
    - `workload: web` (a **Deployment**, not a CronJob: there is no scheduled work)
    - `replicas: 2`, `env.DB_URL`
    - `secretEnv.DB_USER`/`DB_PASSWORD`
    - `configFiles."statements.properties"`, `writablePaths`, `resources`
    - `ingress.enabled: true` with the bank's host and TLS, **only once the authentication question (R1) is settled**
12. **`deploy/platform.yaml`**: smoke paths `/health` → 200, `/statements/accounts` → 200, `/statements/statement?account=HG611000001` → 200, `/statements/statement?account=x` → 400.
13. **kind extras**:
    - `deploy/values-ci.yaml`: `DB_URL` to `jdbc:postgresql://postgres.deps.svc:5432/bankwave`, `replicas: 1`, ingress off.
    - `deploy/kind-deps/`: a postgres Deployment and Service, with `data/seed.sql` in a ConfigMap. The `deps` namespace is not labelled `enforced`, so Kyverno REG-01 does not apply there.
    - `deploy/kind-secrets.env`: `statements-web-db.DB_USER=…`, `statements-web-db.DB_PASSWORD=<test-only>`.
14. **Pipeline caller**: a workflow that calls `.github/workflows/platform-app-pipeline.yml@c56cbe8…` with `app_dir: industries/banking/vmware-wave-1/statements-web` and the same `standards_ref`. The image name becomes `…/otterworks/bank-statements-web`.

**What the first pipeline run would fail**, if it ran against the app as it stands:
- **Unit tests stage**: fails immediately. There is no `Dockerfile` at the app root and no `deploy/`.
- If someone lifts `vm/Dockerfile` as-is:
  - `docker build --target test` fails, because there is no stage named `test`.
  - **Trivy** fails on CRITICAL CVE-2024-1597 in `postgresql-42.2.27.jre7.jar`. It has a fix, so `--ignore-unfixed` does not hide it.
  - The Trivy secret rule `platform-hardcoded-db-password` flags `password="…"` in `context.xml` at HIGH. The step only exits on CRITICAL, so this is a finding rather than a failure, but it breaks the "no credential in the image" requirement.
  - **conftest Dockerfile**: **BASE-01** (`tomcat:8.5-jre8` is not approved; the maven jdk8 build image is approved) and **BASE-02** (no `USER` in the final stage).
- **Probe failure, and where it shows up**: the chart always renders both probes on `/health` (`probes.enabled: true`), so conftest/Kyverno **PROBE-01 passes on the manifests**. The failure appears in the **kind runtime stage**: readiness gets 404, `helm upgrade --install --wait --timeout 4m` times out, and `deploy` fails. The same would happen even if `/health` existed under `/statements` (T11). If someone set `probes.enabled: false` to get past it, PROBE-01 would fail in conftest and at Kyverno admission. So the manifest's "fail the probe policy" is right in spirit; in practice it is a runtime readiness failure.
- In the same kind stage, these are hidden behind the probe failure:
  - Under `runAsUser: 10001` and `readOnlyRootFilesystem`, Tomcat cannot write `logs/`, `work/` or the WAR expansion.
  - log4j cannot open `/var/log/statements`.
  - Without kind-deps and a DB, the JNDI pool cannot connect.

## 5. Test strategy

**What I ran during this review:**
- Built the stand-in image `vm/Dockerfile`, unchanged except that the `FROM` registry was rewritten to `mirror.gcr.io` and Maven Central was mirrored, because Docker Hub and repo1 returned 429 on this VM. The build includes `mvn package`, which ran the 2 JUnit tests in HtmlTest.java, and it succeeded.
- Started `wave1-db` + `stmt-web-01` from `industries/banking/vmware-wave-1/vm/compose.yaml` (the services `make vm-up` starts).
- Observed on http://localhost:8081:
  - `/statements/accounts` → 200, 24 account rows, `Set-Cookie: JSESSIONID=…; Path=/statements; HttpOnly`. Body sha256 `04e7db5f560bda91ba5187cae988313aa34fe09c1308b025402e6b8996aca686`.
  - `/statements/statement?account=HG611000001` → 200, `12 lines, net movement -4694.24`. Body sha256 `50f811333c5b50399025dba93798da807e88e012ef2223fef89653d1907793a6`.
  - The next `/accounts` with the same cookie shows `Last viewed: HG611000001`.
  - `?account=x` → 400.
  - `?account=ZZ99999999` (unknown) → **200 with 0 lines**, not 404.
  - `/health` and `/statements/health` → 404.
  - `/statements/` → 200 (meta-refresh index).
- In the container: uid 0, TZ unset (UTC), Tomcat 8.5.100, OpenJDK 1.8.0_402. Tomcat and app log files were present. `statements_app` is a superuser.

**Characterization tests (before any change).** A pytest + requests suite (Python 3.11 per the standard) with a `BASE_URL` parameter, default `http://localhost:8081`, run after `make vm-up` on the shared `data/seed.sql`. It pins:
- the accounts page: 24 rows, order by `account_id`, holder escaping, title/bank name `Halvergate Bank`, content type `text/html;charset=UTF-8`
- each of the 24 statement pages: rows, `ORDER BY booked, id`, `toPlainString` amounts, date format `yyyy-MM-dd`, summary line
- validation: missing, lowercase, 7-character and 21-character account → 400
- unknown account → 200 with `0 lines, net movement 0`
- the last-viewed flow across two requests with one cookie jar
- the `/statements/` welcome behaviour
- one log line `statement viewed account=…` per statement view, read from the file today and from stdout after the change

Bodies are compared after normalising only the session cookie. The seed's longest statement is 14 lines, so it never reaches `statement.page.size=50`. Add one run with the page size set to 5 to pin `LIMIT` behaviour. Keep the passing output as the baseline.

**Unit tests as the `test` stage.** HtmlTest.java runs in `FROM maven-3.9-jdk17 … AS test` via `mvn -B package`, so `docker build --target test` is the unit step. Add unit tests for `AppConfig` (env/mounted path, defaults), the cookie-based last-viewed, `HealthServlet`, and `StatementDao` against an in-test DataSource. The `StatementDao(DataSource)` constructor at StatementDao.java:26 already allows that.

**Parity report (before = VM stand-in, after = new image on the same seed, locally and on kind via port-forward).**

| Check | Expected result |
|---|---|
| Accounts page body (normalised) | identical |
| 24 statement page bodies | identical |
| Summary line and net movement per account | identical |
| 400 responses (status) for the 4 invalid inputs | identical. The error page body differs between Tomcat 8.5 and 9: accepted difference |
| Unknown account → 200, 0 lines | identical |
| Last-viewed flow | identical rendering. Mechanism `JSESSIONID` session → `lastAccount` cookie: accepted difference |
| `Set-Cookie` headers | accepted difference (no `JSESSIONID`) |
| `/health` | 404 → 200: accepted difference (new endpoint) |
| Bank name and page size from config | identical |
| Statement dates with TZ=UTC vs the production host TZ | identical expected. Verify with one run at `TZ=Europe/London` (or the host's real zone) |
| Log line content | identical text. Location file → stdout: accepted difference |
| Java 8 → 17 number/date formatting | identical expected |

**Kind smoke paths** (from `deploy/platform.yaml`): `/health` 200, `/statements/accounts` 200, `/statements/statement?account=HG611000001` 200, `/statements/statement?account=x` 400, against postgres in `deploy/kind-deps` seeded from `data/seed.sql`. Then run the full characterization suite against the port-forward.

## 6. Effort estimate

**M: 7-10 engineer-days.**

| Work item | Days |
|---|---|
| Characterization suite against the stand-in, baseline recorded | 1-1.5 |
| pom upgrades (Java 17, servlet 4, log4j2 bridge, pgjdbc 42.7.x), unit tests green | 0.5-1 |
| Dockerfile (`test` stage, approved digests, pre-exploded ROOT, Tomcat logging to console, non-root, read-only fs paths, JVM memory flags) | 1-1.5 |
| Datasource and settings from env/mounted file, `secretEnv`, least-privilege DB role, Secrets Manager entry and ExternalSecret coordination | 1.5-2 |
| Stateless last-viewed cookie, `/health` servlet, ROOT context with `/statements/*` mappings | 1 |
| `deploy/` (values, values-ci, kind-deps with seed, kind-secrets, platform.yaml) and the pipeline caller | 1 |
| Pipeline iterations to green, 256Mi tuning, parity report | 1-1.5 |

Assumptions:
- Java 17 / Tomcat 9 is accepted. Waiting for a Java 21 base adds about 0.5-1 day for the jakarta rename and retesting.
- The platform team provides the External Secrets store and the DB role.
- Authentication and ingress exposure (R1) are decided by others. Building an auth layer is out of scope and not counted.
- The production DB is reachable from the cluster.

## 7. Verdict

**replatform.** I agree with the manifest's `expected: replatform`.
- The code is small, has no framework, and is already mostly testable. A `DataSource` constructor exists and the HTML rendering is pure.
- Every host tie can be fixed with container configuration or a change of a few lines: JNDI placeholders, an env/mounted config path, a console appender, a cookie instead of the session, one health servlet.
- An approved base (`tomcat-9-jre17`) keeps the `javax` API, so no framework migration is forced.
- **retain** is not acceptable. The VM stack is end-of-life at every layer (RHEL 7, Java 8, Tomcat 8.5, log4j 1.x), and the JDBC driver has a fixable CRITICAL CVE.
- **rewrite** (for example Spring Boot 3.3) would add risk and days with no functional gain for two read-only pages.

## 8. Risks and open questions

- **R1 No authentication or authorization (security, open question).** `/statements/accounts` lists every customer's account and holder name, and `/statement?account=` returns any account's lines (StatementServlet.java:22-31, AccountsServlet.java:21-30). On the VMs this presumably relies on the online-banking front end and the hardware LB. HOST.md does not say how. Do not enable the ingress until the upstream authentication path on the cluster is defined (for example oauth2-proxy or the online-banking gateway). The NetworkPolicy only admits ingress-nginx and monitoring.
- **R2 Customer data in logs.** Account numbers are logged at INFO (StatementServlet.java:29). Moving to stdout sends them to the cluster log pipeline. Confirm that classification allows it, or mask them.
- **R3 Java 21 vs the approved bases.** The org target is Java 21, but no approved WAR base has it (section 2). Needs a decision from the platform team or wave lead.
- **R4 One path for both probes.** The chart uses `/health` for liveness and readiness. If `/health` checks the DB, a DB outage restarts the pods. If it does not, readiness lets traffic through while the DB is down. Proposed: a DB check with a 1-2 s timeout and `failureThreshold: 6`. Confirm with the platform team whether the chart should allow separate paths.
- **R5 Memory.** 256Mi is tight for Tomcat + JRE 17. Measure, or ask for a namespace limit-range exception.
- **R6 Shared DB credentials.** The VM password is a literal in the repo (vm/conf/context.xml:8, `industries/banking/vmware-wave-1/vm/compose.yaml:10`), and the stand-in role is a superuser. Production should get a new read-only role and a rotated password. The production DB version and its location relative to the cluster are unknown.
- **R7 Production host timezone** is not stated (T20). Verify date rendering with the real zone.
- **R8 URL and cutover.** The public URLs `/statements/...` must stay the same for the online-banking links. Cookie pinning ends at cutover, and users lose "Last viewed" once (acceptable?).
- **R9 log4j 1.x CVEs** may be hidden by `--ignore-unfixed` in the gate. The library must still be removed, not merely pass the scan.
- **DeepWiki.** I asked about `statements-web` / `industries/banking/vmware-wave-1` and `platform/standards`. The index knows neither (it predates these branches) and answered only with the general OtterWorks microservices. This note relies on the code.
- **Not verified:** the production RHEL host configuration (Tomcat `server.xml`, the tomcat service user, TZ), the Tomcat 9 `EnvironmentPropertySource` behaviour on the pinned digest, and the real Trivy output for the target image. No pipeline run was made, per the rules.
