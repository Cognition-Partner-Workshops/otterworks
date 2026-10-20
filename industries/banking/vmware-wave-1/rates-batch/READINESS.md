# rates-batch: wave-1 readiness

Reviewed against `platform/standards/` at commit `c56cbe8f6f4c55242cdece90701e8754566fcc01` (branch `devin/1792540800-platform-standards`; not yet on `main`, unlike what `ESTATE.md` says) and the wave branch at `e42786c9e757919151d390c79429b6f899bfadac`. Paths below are relative to `industries/banking/vmware-wave-1/rates-batch/` unless stated.

## 1. Summary

`rates-batch` is a single-class Java 11 batch job (`RatesJob`, about 90 lines, no runtime dependencies) that root's crontab on `rates-01` starts at 02:00 host-local time. It reads yesterday's hourly tick file from a local spool, writes one CSV of daily open/high/low/close/average-mid per currency pair into a second local spool, and that output directory is exported over NFS to `fx-report` on `report-01`. The code itself is clean and portable: paths and the business date already come in as arguments. What ties it to the VM is everything around the code: cron, the root user, the host clock and zone, two local-disk spools (one written by the feed handler, one read by another app over NFS), a log file the wrapper appends to, and a heap that equals the platform's default memory limit. The platform chart already supports `workload: cronjob` with an explicit `timeZone`, so this is a replatform onto a Kubernetes CronJob. The one real piece of design work is replacing the shared spools, because the chart only mounts `emptyDir` and ConfigMaps.

**Verdict: replatform** (this matches the manifest's `expected: replatform`).

## 2. Runtime and versions

| Item | On the VM today | Source | Proposed target |
|---|---|---|---|
| OS | RHEL 7 (EOL 2024-06) | `HOST.md:5` | Ubuntu Jammy from the approved Temurin base |
| Java | OpenJDK 11 at `/usr/lib/jvm/java-11` | `HOST.md:5`, `vm/run-rates.sh:4` | Java 21 Temurin per `modernization-target-standard`. `base-images.yaml` has **no Java 21 image yet**, so for now: build `maven-3.9-jdk17` (`docker.io/library/maven:3.9-eclipse-temurin-17@sha256:1a352420…8584`), runtime `temurin-17-jre` (`docker.io/library/eclipse-temurin:17-jre-jammy@sha256:b3054a20…a8f1`). Move to 21 once the platform team adds a 21 digest |
| Compiler level | `maven.compiler.release` 11 | `pom.xml:10` | 17 now (21 later). The code uses `String.isBlank` (Java 11+) and nothing that breaks on 17 or 21 |
| Framework | none (plain `main`); no Spring | `pom.xml:13-20` | none. Spring Boot 3.3 adds nothing to a 90-line batch job; keep it plain Java |
| Libraries | JUnit 4.13.2 (test); maven-jar-plugin 3.3.0 | `pom.xml:15-17`, `pom.xml:25-27` | JUnit 4.13.2 is fine, or JUnit 5 if the team prefers; pin surefire |
| Heap | `-Xmx256m` | `vm/run-rates.sh:6` | `-XX:MaxRAMPercentage=75` inside a 256Mi limit |
| Scheduler | root crontab, `0 2 * * *`, host local time | `vm/crontab:3`, `HOST.md:7` | chart `workload: cronjob`, `cronjob.schedule: "0 2 * * *"`, `cronjob.timeZone` set to the bank's zone explicitly |
| Stand-in | `maven:3.9-eclipse-temurin-11` build, `eclipse-temurin:11-jre` + cron, runs as root | `vm/Dockerfile:3,11,19` | not a target image; it only stands in for the VM |

## 3. Host ties

The *Manifest* column says whether `complexity-manifest.json` lists the tie. Rules are the ids in `platform/standards/README.md`. "none (behavior)" means no gate rule catches it, but the move breaks or changes behavior if nobody handles it.

| id | What the host gives the app | file:line | Rule broken | Manifest |
|---|---|---|---|---|
| T1 host-scheduling | root's crontab starts the job at 02:00 | `vm/crontab:3`; `HOST.md:7` | BASE-02 / SEC-01 (runs as root); replaced by a chart CronJob | listed |
| T2 local-state (output spool + NFS) | output written to `/var/spool/rates/out` on local disk; that directory is exported over NFS to fx-report | `vm/run-rates.sh:3`, `vm/run-rates.sh:7`; `src/main/java/com/bank/rates/RatesJob.java:82-89`; `HOST.md:9` | SEC-02 (read-only root fs; only `emptyDir` is writable, and an `emptyDir` disappears with the pod, so fx-report would never see the file) | listed |
| T3 host-timezone | business date = "yesterday" from the host clock and default zone; the host runs on local time | `src/main/java/com/bank/rates/RatesJob.java:60`; `HOST.md:7` | none (behavior): the chart CronJob defaults to `timeZone: Etc/UTC` (`helm/app/values.yaml`), and the container JVM zone defaults to UTC | listed |
| T4 input spool on local disk | `/var/spool/rates/in/ticks-<date>.csv`, dropped overnight by the feed handler on the same host | `HOST.md:8`; `vm/run-rates.sh:7`; `src/main/java/com/bank/rates/RatesJob.java:71-75` | SEC-02 / none (behavior): a pod has no feed-handler disk, so the job exits 1 ("no ticks for …") | **not listed** |
| T5 file logging | the wrapper appends stdout and stderr to `/var/log/rates/rates.log` | `vm/run-rates.sh:7`; `HOST.md:10` | Logs rule ("nothing writes a log file inside the container"); also SEC-02 (write to the read-only root) | **not listed** |
| T6 root user | runs from *root's* crontab | `vm/crontab:1`; `HOST.md:7`; stand-in `vm/Dockerfile:2` (no `USER`) | BASE-02, SEC-01 | **not listed** |
| T7 absolute JDK path | `JAVA_HOME=/usr/lib/jvm/java-11` hard-coded | `vm/run-rates.sh:4`; `HOST.md:5` | BASE-01 (the runtime has to come from the approved base, not a host JDK path) | **not listed** |
| T8 absolute install path / cwd | `cd /opt/rates`, jar at `/opt/rates/lib/rates-batch.jar` | `vm/run-rates.sh:5-6`; `HOST.md:6` | none (behavior): the image layout replaces it | **not listed** |
| T9 heap sized to the host | `-Xmx256m` fixed | `vm/run-rates.sh:6` | RES-01: a 256Mi heap plus metaspace and threads goes over the 256Mi default limit and gets OOMKilled | **not listed** |
| T10 MAILTO alerting | cron mails `ops-batch` on output or failure | `vm/crontab:2` | none (behavior): the cluster sends no mail, so failure alerting needs a replacement (Job-failed alert) | **not listed** |
| T11 EOL OS and old JDK | RHEL 7 (EOL), OpenJDK 11, compiler release 11 | `HOST.md:5`; `pom.xml:10` | BASE-01 only if the base is unapproved (`temurin-11-jre` *is* approved); below the org target of Java 21 | **not listed** |

**Host ties: 11** (3 in the manifest, 8 not in it).

Checked and not tied: there are no credentials, database, network ports, hostnames, TLS, HTTP session state, LDAP or web-server modules. The job opens no sockets.

Not a host tie, but it matters for the gate: the job is not long-running, so PROBE-01 does not apply. `kubernetes.rego` only checks probes on Deployment, StatefulSet and DaemonSet, and the chart adds probes only for `workload: web`. A `/health` endpoint is therefore not needed. Wiring one into a CronJob would be wrong.

## 4. Changes to meet platform/standards (ordered)

1. **Characterization tests first** (see §5). Pin today's output byte-for-byte before touching anything.
2. **Make the business date and zone explicit.** Read `RATES_TZ` (for example `Europe/London`, to be confirmed by ops) and compute yesterday with `LocalDate.now(ZoneId.of(RATES_TZ))`, replacing `RatesJob.java:60`. Keep the explicit date argument (`RatesJob.java:59`) for reruns. Set the same zone in `cronjob.timeZone` so 02:00 is still 02:00 local.
3. **Config from env.** Take the input and output locations from `RATES_IN` and `RATES_OUT` env (or keep them as args from `cronjob.command`). Drop `run-rates.sh` and run `java -XX:MaxRAMPercentage=75 -jar /app/rates-batch.jar …` directly as the container command.
4. **Replace the spools (the main blocker, T2 and T4).** The chart (`helm/app/templates/_helpers.tpl`, `platform-app.volumes`) mounts only `emptyDir` and ConfigMaps, so there is no PVC or NFS option. The options:
   - (a) **S3**, preferred: the feed handler drops ticks under `s3://…/rates/in/`. The job reads them, writes to `/tmp` (`emptyDir`, already in `writablePaths`), then uploads `rates-<date>.csv` to `s3://…/rates/out/` with a write-to-temp-key-then-copy step that replaces today's `ATOMIC_MOVE` (`RatesJob.java:88-89`). This needs the AWS SDK (S3), IRSA, and a `serviceAccountName` the chart does not offer yet. fx-report has to read from S3 too, which is part of its own retain-or-rewrite decision.
   - (b) EFS PVC shared with fx-report. This needs a chart change (PVC volume support) owned by the platform team. It is the least app change, but it keeps the shared-filesystem coupling.
   Either way the order matters: fx-report and the feed handler must move to the new location in the same cutover. Otherwise one side reads an empty spool.
5. **Logging.** Remove the `>> /var/log/rates/rates.log` redirect (`run-rates.sh:7`). The job already writes to stdout and stderr (`RatesJob.java:65,73,90`), so container logs replace the file.
6. **Dockerfile** at the app root:
   - Stage `test`: `FROM docker.io/library/maven:3.9-eclipse-temurin-17@sha256:1a352420f7aba21f5ad08df31bab55f74c013fb491f1ae8ab1dd7ff9ed698584 AS test`, then `mvn -B verify` (unit tests plus the characterization tests on `data/rates/in` copies).
   - Final stage: `FROM docker.io/library/eclipse-temurin:17-jre-jammy@sha256:b3054a20e1a851574cdb1692dd0db5310c647e62214a2a7abecbec1b9e3ae8f1`, copy only the jar, `USER 10001`.
   - No cron, no `ENV` or `ARG` containing secret-like names (SECRET-04). A Maven mirror goes in a settings file, not in an `ARG` named like a credential.
7. **`deploy/values.yaml`**: `app: rates-batch`, `owner`, `costCenter`, `workload: cronjob`, `cronjob.schedule: "0 2 * * *"`, `cronjob.timeZone: <bank zone>`, `cronjob.command`, `env` (`RATES_TZ`, `RATES_IN`, `RATES_OUT`), `writablePaths: [/tmp]`, and resources inside the defaults (requests 100m/128Mi, limits 500m/256Mi). The job uses well under that on 120-line tick files. There is no `secretEnv`: the app has no credentials. With S3, access comes through IRSA and not through keys.
8. **`deploy/platform.yaml`**: `app: rates-batch`. `smoke` paths are not used for a cronjob: `scripts/kind-verify.sh:66-69` runs `kubectl create job --from=cronjob/rates-batch` and waits for `Complete`. Add `deploy/values-ci.yaml` so the kind job processes a fixed date (`2026-10-16`) from seed ticks baked into a test-only location or a `kind-deps/` object store (MinIO or LocalStack) seeded from `data/rates/in/`.
9. **Failure alerting** (replaces MAILTO): a Prometheus alert on `kube_job_status_failed` for the rates-batch job. This is outside the gate, but ops needs it before cutover.
10. **Java 21**: request a `temurin-21-jre` and `maven-3.9-jdk21` digest in `base-images.yaml` through a platform PR, then bump `maven.compiler.release` to 21.

**What the first pipeline run would fail, and why.** No `Dockerfile` or `deploy/` exists at the app root today, so the first run fails at the very first step, "Unit tests (Dockerfile test stage)" (`docker build --target test`). If someone just reuses `vm/Dockerfile`:

- **BASE-01**: both `FROM`s are tag-only. `maven:3.9-eclipse-temurin-11` and `eclipse-temurin:11-jre` have no digest, and the runtime is not the `-jammy` approved image.
- **BASE-02**: there is no `USER`, so it runs as root.
- The test stage is not named `test`.

Even with a compliant image and chart defaults, the conftest gate passes (labels, SEC-01/02, RES-01, and PROBE-01 is not applicable). But **the kind smoke Job fails**:

- With no date argument the job looks for yesterday's ticks, finds none in the pod, and exits 1. This is T4 and `RatesJob.java:72-75`; I reproduced it locally: `no ticks for 2026-10-19 … exit=1`.
- With the wrapper kept, it would also fail writing `/var/log/rates` and `/var/spool/rates/out` on the read-only root (T2, T5).
- At runtime, keeping `-Xmx256m` under a 256Mi limit risks an OOMKill (T9).

## 5. Test strategy

**What I ran (this review).**
- `make vm-build` for `rates-01`: the first attempt hit Docker Hub 429. After pulling the bases from `mirror.gcr.io`, the build failed on Maven Central 429 for `maven-resources-plugin:3.4.0`. `MAVEN_MIRROR` would be needed. The stand-in did not run.
- As a substitute, I compiled `RatesJob.java` with `javac` (host JDK 17) and ran it on the shared seed `data/rates/in/` for 2026-10-14, 2026-10-15 and 2026-10-16. Each day produced 5 pairs from 24 ticks. SHA-256 of the outputs:
  - `rates-2026-10-14.csv` `58c7b413…690d`
  - `rates-2026-10-15.csv` `e2746bf9…2861`
  - `rates-2026-10-16.csv` `0bcf20da…bc2b`
  - Example row for 2026-10-16: `EURUSD,1.086400,1.094290,1.085840,1.087220,1.088876,24`.
- I ran it with no date and no ticks for "yesterday": it exits 1.
- I did not run the JUnit test (no Maven access).

**Characterization tests (pinned on the VM stand-in before any change).**
- `make vm-up` in `industries/banking/vmware-wave-1` (with `MAVEN_MIRROR` set) runs `run-rates.sh` for the three tick days (`make vm-rates`).
- Copy `/var/spool/rates/out/rates-2026-10-1{4,5,6}.csv` out of `rates-01` and commit them as golden files under `src/test/resources/golden/`.
- Add a JUnit test that runs `RatesJob.main` on `data/rates/in` (copied into test resources) into a temp dir, and asserts byte equality with the golden files, including the header, pair order (TreeMap), 6-decimal HALF_EVEN scaling and the trailing newline.
- Add tests for:
  - missing ticks → exit 1 with the message;
  - no args → exit 2;
  - rerun of an existing day → file replaced, not appended;
  - business date for a fixed `Clock` and zone at 02:00 local, including a DST-change night. This needs the small `Clock` injection from change 2, done behind the characterization tests.
- Also pin what fx-report shows for `?day=2026-10-16` (`make vm-smoke`, http://localhost:8086/fx/fx-report.cgi?day=2026-10-16), so the cross-app contract is covered.

**Unit tests → `test` stage.** `RatesJobTest` plus the characterization tests run under `mvn -B verify` in the `test` stage, so `docker build --target test` is the unit step. That is why the seed tick files and golden files must sit inside the app build context.

**Parity report rows (before = VM stand-in, after = CronJob on kind/EKS).**

| Check | Before | After |
|---|---|---|
| sha256 of `rates-2026-10-14.csv` | `58c7b413…` | must be identical |
| sha256 of `rates-2026-10-15.csv` | `e2746bf9…` | identical |
| sha256 of `rates-2026-10-16.csv` | `0bcf20da…` | identical |
| pairs per day / ticks per pair | 5 / 24 | identical |
| business date picked at 02:00 local with no arg | host-local yesterday | identical under `RATES_TZ` + `cronjob.timeZone` |
| missing-ticks exit code | 1 | Job `Failed`, exit 1 |
| fx-report page for 2026-10-16 (close, avg, range, chg %) | VM stand-in | identical, reading the new store |
| log location | `/var/log/rates/rates.log` | stdout (accepted difference: platform rule) |
| run user | root | uid 10001 (accepted difference) |

**kind-cluster smoke.** `kind-verify.sh` creates a Job from the CronJob and waits for `Complete` within 180 s. Through `values-ci.yaml` the Job runs for `2026-10-16` against `kind-deps/` (MinIO or LocalStack seeded with `data/rates/in`). A follow-up check compares the produced object's sha256 with `0bcf20da…`.

## 6. Effort estimate

**M: 5-8 engineer-days**

| Work item | Days |
|---|---|
| Characterization tests and golden files (stand-in up with a Maven mirror, DST/zone tests) | 1-1.5 |
| Zone/clock and env config, drop the wrapper, heap flags | 0.5 |
| Spool replacement (S3 client, IRSA/service account, temp-then-copy publish), coordinated with fx-report and the feed handler | 2-3.5 |
| Dockerfile (`test` stage, digest-pinned JDK 17 bases, USER 10001) | 0.5 |
| `deploy/values.yaml`, `values-ci.yaml`, `platform.yaml`, `kind-deps/` with seeded ticks | 0.5-1 |
| Pipeline runs, parity report, Job-failure alert | 0.5-1 |
| **Total** | **5-8** |

Assumptions:
- S3 (or another object store) is acceptable to the bank and the feed handler team.
- fx-report's own move or rewrite is estimated separately; only the cutover coordination is counted here.
- The chart gets (or tolerates) a `serviceAccountName` for IRSA.
- Java 21 bases are added by the platform team. Until then, the job ships on approved Temurin 17.
- If option (b), EFS PVC, is chosen instead, subtract about 1.5 days of app work and add a platform chart change.

## 7. Verdict

**replatform.** I agree with the manifest's `expected: replatform`.

Reasoning:
- The business logic is small, deterministic, dependency-free and already parameterised by directories and date. It needs no rewrite.
- It is not worth retaining on RHEL 7, which is EOL.
- The platform chart already has a first-class CronJob mode with `timeZone`, `concurrencyPolicy: Forbid` and non-root, read-only defaults that fit a batch job.
- Every host tie has a standard replacement:
  - cron → CronJob;
  - host zone → explicit `RATES_TZ` and `timeZone`;
  - log file → stdout;
  - root → uid 10001;
  - heap → `MaxRAMPercentage`.
- The only non-trivial change is moving off the shared local/NFS spools. That is an integration change, not a reason to rewrite.

## 8. Risks and open questions

- **Biggest blocker**: the output spool is local disk shared with fx-report over NFS (`vm/run-rates.sh:7`, `src/main/java/com/bank/rates/RatesJob.java:82-89`). The platform chart mounts only `emptyDir`/ConfigMap, so shared storage needs S3 (app change plus IRSA) or a platform chart change for a PVC. fx-report (expected retain-or-rewrite) must switch at the same time.
- Which zone is "local time" on `rates-01`? The tick timestamps carry no offset (`data/rates/in/ticks-*.csv`, e.g. `2026-10-14T00:15:00`), while the unit test uses `Z`. Is a tick file a local or a UTC day? This decides whether `RATES_TZ` is a business zone or UTC, and how DST nights behave (23- or 25-hour days; 02:00 local is skipped or repeated on transition nights in some zones).
- Who owns the feed handler that writes the input spool (T4), and can it write to S3? If it stays on a VM, the CronJob depends on a cross-network drop.
- The chart has no `serviceAccountName` and sets `automountServiceAccountToken: false`. IRSA's projected token should still be injected by the EKS webhook, but this needs confirming with the platform team.
- There are no Java 21 images in `base-images.yaml`, which conflicts with the org target (Java 21). Shipping on 17 is an interim step that needs sign-off.
- Rerun by hand (`HOST.md:11`) becomes `kubectl create job --from=cronjob/rates-batch` with a date override. Ops runbooks need updating.
- MAILTO alerting disappears. Without a Job-failure alert, a missed night goes unnoticed until the FX desk opens the report.
- A malformed tick line throws and fails the whole day (`RatesJob.java:49-52`). That is current behavior and should be kept (pinned), not "fixed", during the move.
- DeepWiki (asked about rates-batch, `industries/banking/vmware-wave-1` and the platform standards): the index has nothing on either. It said the path, `base-images.yaml` and the BASE-01/SEC-01/PROBE-01 rules are not in its context, and described the unrelated analytics-service `UsageRollupJob` CronJob instead. It was not useful; this review relies on the code.
- The stand-in could not be built in this review (Docker Hub and Maven Central returned 429), so the golden hashes above come from a direct `javac` run of the same source on JDK 17. They must be re-pinned against `make vm-up` output on JDK 11.
