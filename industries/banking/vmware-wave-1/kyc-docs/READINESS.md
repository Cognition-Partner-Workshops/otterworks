# kyc-docs: wave-1 readiness

Reviewed against: wave branch `devin/1792545000-bank-wave1` @ `e42786c9e757919151d390c79429b6f899bfadac`, platform standards `devin/1792540800-platform-standards` @ `c56cbe8f6f4c55242cdece90701e8754566fcc01` (`platform/standards/README.md`, `base-images.yaml`, `helm/app`, `policy/`, `examples/sample-service`, `.github/workflows/platform-app-pipeline.yml`), and the org modernization target standard. All paths below are relative to `industries/banking/vmware-wave-1/kyc-docs/` unless stated otherwise.

## 1. Summary

`kyc-docs` is a small Spring Boot 2.3 service (three classes, two endpoints) that takes identity documents from the onboarding flow and keeps them per customer for compliance. On `kyc-01` it serves HTTPS itself on 8443 from a self-signed keystore, writes every uploaded document to local disk under `/var/kyc/uploads` (backed up only by the nightly VM snapshot), logs to `/var/log/kyc`, and has no health endpoint (the load balancer only checks that TCP 8443 accepts a connection). It has no database and no runtime dependency on the other wave apps; it shares only the customer ids (`HG611...`) with `data/seed.sql`. The code is clean and easy to move: the Java changes are a Boot 3.3 upgrade (no `javax.*` imports to rename), a `/health` endpoint, plain HTTP on 8080 behind the shared ingress, stdout logging, and a storage port so documents go to object storage instead of the pod's disk. The one non-trivial item is the document store: the platform chart only offers `emptyDir` for writable paths, so KYC documents must move to S3 (or another durable store), the existing files on `kyc-01` must be migrated with checksums, and the backup and retention the VM snapshot gives today must be replaced. As it stands, the first pipeline run fails at the unit-test stage (no `Dockerfile` with a `test` stage at the app root) and, after a lift-and-shift Dockerfile, on BASE-01/BASE-02, on the probes and very probably on the Trivy CRITICAL gate.

**Verdict: replatform** (agrees with the manifest's `expected: replatform`). Effort: **M, 6.5-10 engineer-days**.

## 2. Runtime and versions

| Item | Today (VM / build files) | Source |
|---|---|---|
| OS | RHEL 8 | `HOST.md:5` |
| Java | OpenJDK 11 on the VM; `java.version` 11; stand-in runs Temurin 11.0.32 | `HOST.md:5`, `pom.xml:15`, `vm/Dockerfile:11` |
| Framework | Spring Boot 2.3.12.RELEASE (OSS support ended 2021) | `pom.xml:5-10` |
| Server | Embedded Tomcat 9.0.46 with its own TLS connector on 8443 | `application.properties:1-6`, fat JAR contents |
| Key libraries (from the built JAR) | spring-core / spring-webmvc 5.2.15.RELEASE, jackson-databind 2.11.4, logback-classic 1.2.3, log4j-api / log4j-to-slf4j 2.13.3 (API bridge only, not log4j-core), snakeyaml 1.26 | `BOOT-INF/lib` of the stand-in JAR |
| Test libraries | spring-boot-starter-test (JUnit 5, vintage excluded) | `pom.xml:22-32` |
| Build | Maven 3.9, `mvn package -DskipTests` | `vm/Dockerfile:3-9` |
| Process manager | systemd unit, user `kyc`, `-Xmx512m`, `Restart=on-failure` | `vm/kyc-docs.service:6-10` |
| Packaging | fat JAR `/opt/kyc/kyc-docs.jar` | `HOST.md:5`, `pom.xml:35` |

**Proposed target**

- Java **17** (Temurin) and Spring Boot **3.3.x** (jakarta). The org standard asks for Java 21, but `base-images.yaml` on the standards branch has no Java 21 image: the newest approved are `maven-3.9-jdk17` (build) and `temurin-17-jre` (runtime). Boot 3.3 runs on 17, so the app can pass the gate now on 17 and move to 21 by a one-line `FROM` change once the platform team adds a `temurin-21-jre` / `maven-3.9-jdk21` digest (open question 1). `temurin-11-jre` is approved too, but staying on 11 means staying on Boot 2.x, which is end of life and is the likely source of Trivy CRITICAL findings.
- Base images (exact digests from `base-images.yaml`):
  - `test` and build stage: `docker.io/library/maven:3.9-eclipse-temurin-17@sha256:1a352420f7aba21f5ad08df31bab55f74c013fb491f1ae8ab1dd7ff9ed698584`
  - runtime stage: `docker.io/library/eclipse-temurin:17-jre-jammy@sha256:b3054a20e1a851574cdb1692dd0db5310c647e62214a2a7abecbec1b9e3ae8f1`
- Libraries: whatever Boot 3.3.x manages (Spring Framework 6.1, Tomcat 10.1, Jackson 2.17, Logback 1.5), plus `spring-boot-starter-actuator` for `/health` and AWS SDK v2 `s3` for the document store.

## 3. Host ties

Line numbers verified with `nl -ba` on commit `e42786c`. "New" = not listed in `complexity-manifest.json`.

| # | Id | What the host gives the app | file:line | Platform rule it breaks | In manifest |
|---|---|---|---|---|---|
| 1 | local-state | A durable local disk: every upload is written to `/var/kyc/uploads/<customer>/` and listed from there | `src/main/resources/application.properties:7`; `src/main/java/com/bank/kyc/DocumentStore.java:22-23`, `:31-34`, `:45-48`; `HOST.md:7` | SEC-02 (read-only root fs; the chart's only writable paths are `emptyDir`, which is lost when the pod goes away) | yes |
| 2 | snapshot-backup | Backup and retention of the documents through the nightly VM snapshot | `HOST.md:7` | No gate rule; the cluster has no equivalent, so a compliance requirement is silently dropped | **new** |
| 3 | self-managed-tls | HTTPS terminated in the app with a self-signed, ten-year keystore at `/etc/kyc/keystore.p12` | `src/main/resources/application.properties:2-6`; `vm/Dockerfile:12-14`; `HOST.md:6` | PROBE-01 / smoke (the chart's probes and the kind smoke call plain HTTP on the `http` port), NET-01 (TLS belongs on the shared ingress with cert-manager), SEC-02 (absolute host path) | yes |
| 4 | keystore-credential | Keystore password from `/etc/kyc/kyc.env` via systemd, with `changeit` as a default in source and in the keytool call | `src/main/resources/application.properties:5`; `vm/Dockerfile:14`; `vm/kyc-docs.service:8`; `HOST.md:6` | README "bakes in no credential" / SECRET-0x (a default password ships in the JAR); needs a `secretEnv` ref if any secret remains | **new** |
| 5 | fixed-port | Port 8443 fixed in config and exposed by the image; the LB targets 8443 | `src/main/resources/application.properties:1`; `vm/Dockerfile:16`; `HOST.md:9` | Chart contract (`containerPort` 8080 named `http`, Service 80 ClusterIP, NET-01) | **new** |
| 6 | missing-probe | Health judged by a TCP connect from the load balancer; no actuator, no status endpoint | `pom.xml:17-33` (only `starter-web` and `starter-test`); `src/main/java/com/bank/kyc/DocumentController.java:14` (only `/documents`); `HOST.md:9` | PROBE-01 (rendered probes would point at a `/health` that returns 404; verified on the stand-in) | yes |
| 7 | file-logging | Writable `/var/log/kyc/kyc-docs.log` | `src/main/resources/application.properties:9`; `HOST.md:8` | README "logs on stdout and stderr", SEC-02 (read-only root fs) | yes |
| 8 | process-manager | systemd starts, restarts and runs the JVM as named user `kyc`, loading env from a host file | `vm/kyc-docs.service:6-10`; `HOST.md:5`; stand-in has no `USER` at all (`vm/Dockerfile:11-17`, runs as uid 0) | BASE-02 (numeric non-root USER), SEC-01 | **new** |
| 9 | jvm-heap | A VM with room for `-Xmx512m`; the stand-in used ~298 MiB just after a few requests | `vm/kyc-docs.service:9`; `vm/Dockerfile:17` | RES-01 (limit range 500m / 256Mi; a 512m heap cannot fit) | **new** |
| 10 | eol-runtime | RHEL 8 + OpenJDK 11 + Spring Boot 2.3.12 (Tomcat 9.0.46, Spring 5.2.15) | `pom.xml:8`, `pom.xml:15`; `HOST.md:5`; `vm/Dockerfile:3`, `:11` | Org target (Java 21/17, Boot 3.3); pipeline Trivy gate (`--severity CRITICAL --ignore-unfixed`) very likely fails on these versions (not run here, see risks) | **new** |
| 11 | host-identity | Clients reach `kyc-01:8443` and trust a cert issued to `CN=kyc-01` | `vm/Dockerfile:13`; `HOST.md:6`, `:9` | NET-01 (new hostname on the shared ingress, cert from cert-manager); callers' trust stores/pins must change | **new** |
| 12 | network-perimeter-auth | No authentication on upload or list; access control is the VM's network position behind the LB | `src/main/java/com/bank/kyc/DocumentController.java:13-35` | No gate rule; the chart NetworkPolicy admits ingress-nginx, monitoring and every pod in the namespace (`podSelector: {}`), and enabling the ingress makes the API reachable from outside | **new** |
| 13 | multipart-tmp | Tomcat spools multipart uploads (up to 10 MB) to `java.io.tmpdir` on the host disk | `src/main/resources/application.properties:8` | SEC-02 (needs `/tmp` as `emptyDir`; the chart default `writablePaths: [/tmp]` covers it, and the 10 MB spool counts toward pod ephemeral storage) | **new** |

Checked and **not** present: database or JNDI datasource (none), committed DB credentials (none), `/etc/hosts` names (none), cron or batch scheduling (none, long-running web workload), NFS or shared filesystem (none), session state or sticky sessions (none: stateless REST), web-server modules (none), host timezone (none: file names use `Instant.now().toEpochMilli()` at `DocumentStore.java:33`, which is zone-independent; log timestamps follow the host zone, UTC on the stand-in).

Manifest gaps: rows 2, 4, 5, 8, 9, 10, 11, 12, 13 (nine of thirteen). The four manifest conditions (rows 1, 3, 6, 7) are confirmed, but the manifest points `self-managed-tls` only at `vm/Dockerfile`; the code-side tie is `application.properties:1-6`, and `missing-probe` points at `pom.xml` while the observable symptom is in `HOST.md:9`.

## 4. Changes to meet platform/standards

Ordered; each step keeps the characterization suite (section 5) green.

1. **Characterization tests first** against the stand-in (section 5), stored with their passing output before any code change.
2. **Upgrade to Spring Boot 3.3.x / Java 17**: bump the parent in `pom.xml:5-10` and `java.version` at `pom.xml:15`. No `javax.*` imports exist in `src/main`; `Collectors.toList()` and `@Value` are unchanged. Run the unit tests and characterization suite.
3. **Health endpoint**: add `spring-boot-starter-actuator`, expose only `health`, and map it to `/health` (`management.endpoints.web.base-path=/`, `management.endpoints.web.path-mapping.health=health`, `management.endpoints.web.exposure.include=health`). Readiness includes the document store check (bucket reachable); liveness stays process-only (`management.endpoint.health.group.liveness/readiness`). The chart already wires `/health` to both probes on the `http` port.
4. **Drop in-app TLS**: delete `server.ssl.*` (`application.properties:2-6`), set `server.port=${PORT:8080}`, and add `server.forward-headers-strategy=framework` so the app sees the ingress scheme. TLS terminates on the shared ingress-nginx with cert-manager (`ingress.tls: true` in the chart). The keystore and its password disappear, which removes host ties 3, 4, 5 and 11 from the image.
5. **Config from env**: replace absolute paths with env-backed properties (`KYC_STORE=s3|fs`, `KYC_BUCKET`, `KYC_PREFIX`, `AWS_REGION`, optional `KYC_S3_ENDPOINT` for the kind run, `KYC_UPLOAD_DIR` for the filesystem adapter in unit tests). No default credential anywhere.
6. **Document store on S3** (replaces host ties 1 and 2): extract a `DocumentStore` interface from `DocumentStore.java`, keep the current filesystem implementation for tests, add an S3 implementation with the same validation (`CUSTOMER` regex, `KINDS`, extension rules) and the same response shape; key `<customer>/<kind>-<epochMillis><ext>`, list with `ListObjectsV2` on prefix `<customer>/`, sorted like today. Bucket: SSE-KMS, versioning, Block Public Access, lifecycle/Object Lock retention agreed with compliance, tagged with the run token and `Expires` for wave runs. Credentials by workload identity (IRSA or EKS Pod Identity, open question 3); only if that is impossible, static keys through `secretEnv` refs to an External Secrets-backed Secret, never values.
7. **Logging to stdout**: delete `logging.file.name` (`application.properties:9`); Boot logs to the console by default. Optionally JSON console format (Boot 3.4+) or a logstash encoder.
8. **Memory within 256Mi**: drop `-Xmx512m`; run with `JAVA_TOOL_OPTIONS="-XX:MaxRAMPercentage=60 -XX:+UseSerialGC -Xss512k -XX:ReservedCodeCacheSize=48m -XX:MaxMetaspaceSize=96m"`, stream uploads straight to S3 (no full in-memory buffering), keep `max-file-size=10MB`. Measure RSS under the characterization load; if it cannot hold under 256Mi, ask the platform team for a namespace limit-range exception rather than raise the limit silently.
9. **Dockerfile at the app root** (`kyc-docs/Dockerfile`, the `vm/Dockerfile` stays as the stand-in):
   - stage 1 `FROM <maven-3.9-jdk17@sha256:...> AS test`: copy `pom.xml`, `mvn dependency:go-offline`, copy `src`, `mvn -B verify` (unit tests run, so `docker build --target test` is the unit step);
   - stage 2 `FROM <temurin-17-jre-jammy@sha256:...>`: `COPY --from=test /src/target/kyc-docs.jar /app/kyc-docs.jar`, `USER 10001`, `EXPOSE 8080`, `ENTRYPOINT ["java","-jar","/app/kyc-docs.jar"]`. No `ENV`/`ARG` whose name matches `password|secret|token|api_key` (SECRET-04). `MAVEN_MIRROR` as an `ARG` is fine.
   - A Docker `HEALTHCHECK` on `/health` is optional (the org container baseline asks for one; it needs a client such as `curl` in the runtime image, to be confirmed for the approved digest); the chart probes are what the platform gate checks.
10. **`deploy/values.yaml`**: `app: kyc-docs`, `owner: <KYC platform team>`, `costCenter: <finance code>` (both still to be supplied, open question 6), `containerPort: 8080`, `env` with the non-secret settings, `secretEnv` only if step 6 falls back to static keys, `writablePaths: [/tmp]`, resources at or under `requests 100m/192Mi`, `limits 500m/256Mi`, `probes.initialDelaySeconds: 20` (JVM start), `replicas: 2` once on S3 (the app is then stateless). `deploy/values-eks.yaml` for the bucket name and region.
11. **`deploy/platform.yaml` smoke paths**: `GET /health` → 200, `GET /documents/HG611000001` → 200, `GET /documents/bad..id` → 400 (validation still in place). The pipeline smoke only does GETs, so the upload round-trip lives in the parity suite.
12. **kind run**: `deploy/kind-deps/` with a MinIO `Deployment` + `Service` (the `deps` namespace is not policy-enforced), a job or init step that creates the bucket, `deploy/values-ci.yaml` pointing `KYC_S3_ENDPOINT` at `http://minio.deps:9000` with path-style access, and `deploy/kind-secrets.env` with throwaway MinIO keys referenced through `secretEnv` (test-only; never real values).
13. **Workload type**: `Deployment` (`workload: web`). No CronJob: the app has no scheduled work. Nightly backup is replaced by S3 versioning/replication, not by a job.
14. **Data migration and cutover**: one-off copy of `/var/kyc/uploads/**` to the bucket with a SHA-256 manifest, verified object-by-object; freeze uploads (or dual-write) for the cutover window; move the onboarding flow to the ingress hostname; keep `kyc-01` read-only until the parity report is signed off.
15. **Access control** (host tie 12): at minimum keep the ingress disabled or IP-restricted and allow only the onboarding flow's namespace in `networkPolicy.ingressNamespaces`; decide whether to add service-to-service authentication before go-live (open question 4).

**What the first pipeline run would fail, and why**

- *App folder as it is today*: the **Unit tests** step (`docker build --target test kyc-docs/`) fails immediately because there is no `Dockerfile` at the app root; Container build fails for the same reason; Trivy, policy and kind are skipped (`if:` on build success), so the gate reports failure without naming a rule.
- *If `vm/Dockerfile` were copied to the root (lift and shift)*: Unit tests fail (no stage named `test`; the build also uses `-DskipTests`, `vm/Dockerfile:9`). Conftest Dockerfile policy: **BASE-01** twice (`vm/Dockerfile:3` and `:11`, tags without digests) and **BASE-02** (no `USER` in the final stage; the stand-in runs as root). Manifest policy cannot render (no `deploy/values.yaml`; the chart `required`s `app`, `owner`, `costCenter`). Trivy CRITICAL gate: expected to fail on Tomcat 9.0.46 / Spring 5.2.15 (not verified locally, Trivy is not installed on this VM).
- *With a compliant Dockerfile and `deploy/` but no code change*: conftest on the rendered chart passes (the chart renders probes, labels, securityContext and resources by default), but the **kind runtime stage fails**: the keystore at `/etc/kyc/keystore.p12` does not exist, so Tomcat's TLS connector fails at start; if a keystore were baked in, the app would listen on 8443 HTTPS while the probes and the smoke call HTTP on port `http`/8080, `/health` returns 404 even on the right port, `helm --wait` times out, and the result is a **PROBE-01**-class runtime failure. The log file on the read-only root fs and the 512m heap against a 256Mi limit (**RES-01** in practice, OOMKill) would follow.

## 5. Test strategy

**Characterization tests (before any change).** Start the stand-in (`make vm-up` in `industries/banking/vmware-wave-1`, or only `docker compose -f vm/compose.yaml up -d --build kyc-01`) and pin against `https://localhost:8085` (`curl -k`). Customer ids come from the shared seed (`data/seed.sql`, e.g. `HG611000001`, `HG611000002`). Behavior observed on the stand-in during this review:

| Request | Stand-in result |
|---|---|
| `GET /documents/HG611000001` (fresh) | 200 `[]` |
| `POST /documents/HG611000001?kind=passport` with `file=scan.PDF` (100 bytes) | 201 `{"customer":"HG611000001","kind":"passport","file":"passport-<epochMillis>.pdf","bytes":100}` |
| `GET /documents/HG611000001` after upload | 200 `["passport-<epochMillis>.pdf"]` |
| `POST ...?kind=selfie` | 400 `{"error":"unknown document kind"}` |
| `POST /documents/bad..id?kind=passport` and lowercase `hg611000002` | 400 `{"error":"bad customer id"}` |
| `POST` without `kind` | 400 (Spring default error body) |
| `POST` with an 11 MB file (limit 10 MB) | **500** (Spring default error body; `MaxUploadSizeExceededException` is not handled) |
| `GET /health` | 404 |
| plain `http://` on the TLS port | 400 "This combination of host and port requires TLS." |
| certificate | `CN=kyc-01`, valid ten years |

The suite (JUnit 5 + RestAssured or a pytest/httpx script) takes a base URL, so the same tests run unchanged against the stand-in and the replatformed app (port-forward on kind, the ingress host on EKS). Volatile fields (`<epochMillis>` in file names, timestamps in error bodies) are normalized by regex, never dropped. The 500 on oversize is pinned as current behavior; changing it to 413 would be an accepted, documented difference, not a silent one.

**Unit tests → `test` stage.** `src/test/java/com/bank/kyc/DocumentStoreTest.java` (2 tests: save and list under the customer, reject path tricks and unknown kinds). Run in this review with `mvn -B test` in `maven:3.9-eclipse-temurin-11` (via a Maven Central mirror, because Central and Docker Hub both returned 429): **2 run, 0 failures, 0 errors**. They become the `test` stage (`mvn -B verify`), extended with a contract test that both the filesystem and the S3 store implementations must pass (S3 against Testcontainers MinIO or an in-memory fake), and a `@SpringBootTest` + `MockMvc` test for `/health` and the controller error mapping.

**Parity report** (one row per check, before = stand-in, after = replatformed app):

| Check | Compared |
|---|---|
| Upload response shape | JSON keys and order, `bytes`, `file` pattern `<kind>-\d{13}<ext>` |
| Extension mapping | `.PDF`, `.jpg`, `.jpeg`, `.png`, `run.sh`, no name → `.pdf/.jpg/.jpeg/.png/.bin/.bin` |
| Listing | same names, same sort order, empty list for unknown customer |
| Validation | status and body for bad customer, unknown kind, missing `kind`, missing `file` |
| Size limit | 10 MB accepted, 10 MB + 1 rejected (status before vs after) |
| Stored bytes | SHA-256 of every uploaded file equals the SHA-256 of the stored object |
| Migration | object count and SHA-256 manifest of `/var/kyc/uploads` vs the bucket, per customer |
| Health | 404 before vs 200 after (accepted difference: new endpoint) |
| Transport | HTTPS self-signed on 8443 vs HTTPS on the ingress with a cert-manager certificate (accepted difference) |
| Logs | one `stored <kind> for <customer> (<n> bytes)` line per upload, on stdout after |
| Restart durability | document still listed after `kubectl rollout restart` (would fail on emptyDir; must pass on S3) |
| Memory | RSS under the upload load vs the 256Mi limit, no OOMKill |

**Kind-cluster smoke paths** (`deploy/platform.yaml`): `/health` 200, `/documents/HG611000001` 200, `/documents/bad..id` 400, with MinIO from `deploy/kind-deps/`. The upload round-trip and the restart durability check run from the characterization suite against the port-forward, since the pipeline smoke only issues GETs.

## 6. Effort estimate

| Work item | Engineer-days |
|---|---|
| Characterization suite against the stand-in, normalization, stored baseline | 1-1.5 |
| Boot 3.3 / Java 17 upgrade, actuator `/health`, HTTP on 8080, stdout logging, env config | 1-1.5 |
| S3 document store (interface, adapter, contract tests, MinIO for kind) and identity wiring (IRSA / Pod Identity or `secretEnv` fallback) | 2-3 |
| Dockerfile (`test` stage, pinned bases, `USER 10001`), `deploy/values*.yaml`, `platform.yaml`, `kind-deps/`, `kind-secrets.env`, memory tuning to 256Mi | 1-1.5 |
| Pipeline iterations (Trivy, conftest, kind), fixing what they find | 0.5-1 |
| Data migration with checksum manifest, cutover runbook, parity report, caller hostname/cert change | 1-1.5 |
| **Total** | **6.5-10** (M) |

Assumptions: one engineer who knows Spring Boot; the S3 bucket, KMS key and IAM role are provisioned by the platform/infra team through Terraform within the window (not counted); retention rules come from compliance without a redesign; the onboarding caller can switch hostname and trust a public CA certificate; no authentication layer is added in this wave (if it is, add 2-4 days); Java 17 is accepted until a Java 21 base image is approved (moving to 21 later is under half a day).

## 7. Verdict

**replatform.** The application logic is three small classes with good input validation and no framework-specific baggage, no `javax.*` code to migrate, no database, no sessions and no schedule, so a rewrite buys nothing. Retain is not justified either: it sits on an end-of-life Boot 2.3 / Java 11 / RHEL 8 stack and every one of its host ties has a standard platform replacement (ingress TLS, actuator health, stdout logs, env config, object storage). The only change beyond configuration is moving documents from local disk to S3, which is a contained adapter behind the existing `DocumentStore` class plus a one-off data migration. **I agree with the manifest's `expected: replatform`**, but the manifest understates the work: it lists 4 conditions where 13 host ties exist, and it does not mention the document backup/retention, the heap that does not fit the 256Mi limit, the end-of-life runtime, or the absence of authentication.

## 8. Risks and open questions

1. **Java 21 vs approved bases.** The org standard targets Java 21; `base-images.yaml` has no Java 21 image. Proposal: ship on 17 now and ask the platform team to approve `temurin-21-jre` and `maven-3.9-jdk21` digests.
2. **Biggest blocker: durable document storage.** `DocumentStore.java:22-23`/`:31-34` with `application.properties:7` write regulated documents to local disk; the platform chart has no PVC support, only `emptyDir`, so documents would be lost on every pod restart. S3 needs a bucket, KMS key, IAM role and retention policy that do not exist yet.
3. **Workload identity in the chart.** `helm/app` sets `automountServiceAccountToken: false` and has no `serviceAccountName` value. Whether IRSA or EKS Pod Identity works for the namespace's default service account under this chart needs to be confirmed with the platform team; the fallback (static keys via `secretEnv`) passes the gate but is weaker.
4. **No authentication** on upload or list (`DocumentController.java:13-35`). On the VM, network position was the control. On the cluster, the chart NetworkPolicy admits every pod in the namespace plus ingress-nginx and monitoring, and the EKS stage enables a public ingress host. KYC documents are sensitive personal data: decide before go-live whether to keep the ingress disabled / IP-allow-listed or add service-to-service auth (mTLS or OAuth2 client credentials).
5. **Trivy CRITICAL gate.** Not run here (Trivy is not installed on this VM). Tomcat 9.0.46 and Spring 5.2.15 have known critical advisories with fixes available, so a Boot 2.3 image very probably fails the gate; the Boot 3.3 upgrade is assumed to clear it.
6. **Owner and cost centre** for `deploy/values.yaml` are not recorded anywhere in the wave folder.
7. **Callers and certificate trust.** The onboarding flow is outside the wave; it is not known whether it pins the `CN=kyc-01` certificate or the hostname, or retries on failure during cutover.
8. **Existing data volume and retention.** Size and count of files under `/var/kyc/uploads` on the real `kyc-01`, the snapshot retention period, and any legal hold are unknown; they size the migration and the S3 lifecycle.
9. **Memory.** The stand-in used about 298 MiB with `-Xmx512m`; fitting under 256Mi with 10 MB multipart uploads needs measurement. A limit-range exception may be required.
10. **Behavior quirks to keep or change deliberately**: oversize upload returns 500 (not 413); two uploads of the same kind in the same millisecond overwrite each other (`StandardCopyOption.REPLACE_EXISTING`, `DocumentStore.java:34`); content is not checked against the claimed extension.
11. **DeepWiki** (`devin_ask_wiki_question` on `Cognition-Partner-Workshops/otterworks`) returned nothing about `kyc-docs`, the `vmware-wave-1` estate or `platform/standards` (base images, conftest/Kyverno); it only described the existing OtterWorks Helm charts under `infrastructure/helm/`. The index predates these branches, so this note relies on the code.

### What was run during this review

- `mvn -B test` in `maven:3.9-eclipse-temurin-11` (Central mirror): 2 tests, 0 failures.
- `docker compose -f vm/compose.yaml up -d --build kyc-01` with `MAVEN_MIRROR` set and the base images pulled from `mirror.gcr.io` (Docker Hub returned 429): stand-in up on `https://localhost:8085`; the requests in section 5 were issued and the results recorded; container removed afterwards.
- No AWS, ECR or Kubernetes resources were created.
