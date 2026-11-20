# Core SonarQube SAST baseline

This Phase 0 Sprint 1 baseline uses the organization-standard SonarQube SAST scanner for the core 13 OtterWorks deployables: 11 backend services and the client app and admin dashboard. It is read-only with respect to application code, performs no dependency installs or builds, and preserves intentionally planted demo defects. Everything outside the explicit core roots is excluded, along with nested scripts, dependencies, build output and lockfiles; test files are classified separately rather than treated as production sources. Findings are raw scanner output, not a claim that every language is covered or that every reported issue is exploitable. See [TRIAGE.md](TRIAGE.md) for triage.

## Run

From the repository root, with Docker Engine and Docker Compose available on Linux:

```sh
make sast-baseline
# Optional output and runtime overrides (relative paths are resolved from the caller):
OUT="$PWD/my-baseline" RUNTIME_DIR="$PWD/my-runtime" make sast-baseline
```

The runner resolves the repository from its own location and defaults exports to `security/sast/baseline/`. That directory contains only `issues.json`, `hotspots.json`, `scan-meta.json`, `quality-profiles.json`, and `analyzed-files.json`. Logs, the generated Compose override, a scanner-index inventory and a generated report go to ignored `security/sast/.runtime/`, not the baseline directory. Metadata paths are repository-relative. `issues.json` retains the legacy type/severity fields and the newer impacts/software-quality and clean-code fields without normalization loss.

Each run recreates the dedicated `otterworks-core-baseline` local Compose instance from scratch, changes the default administrator password to a random value, mints an ephemeral local token and leaves the server running at `http://127.0.0.1:9000`. Neither generated credential is written to disk or displayed. Port 9000 must be available to this stack. The runner uses the existing `security/ingest/docker-compose.sonarqube.yml` with a generated image/healthcheck override: the pinned image has `curl`, not the original healthcheck's `wget`. No repository configuration is changed at runtime. JVM analysis uses an empty binaries directory. There is no dependency or test execution step.

## Pinned baseline

- Application commit: `4f4654d882fd8691b9c40ad21a7a06f013604537`.
- SonarQube Community Build: **26.11.0.134175**; image `sonarqube@sha256:c3c729d9d797467692445bd718f1e8c8e1d34b7607469308e8e9cffe804f36d1`.
- SonarScanner CLI: **8.4.0.16527**; image `sonarsource/sonar-scanner-cli@sha256:6e6eca4d552695a98fb7dab84f0c1bd0885ebbfe272654d1552e24bd7f452d51`.
- API/export runtime: Python 3.12 Alpine image `python@sha256:c5ba3deef00c7758561a0f03c26f44f10589263d40e732b8748e0d1f38f6dd89`.
- Project: `otterworks-core-baseline`.
- Factory-default profiles in this version are named **Sonar way core**, and **Sonar way comprehensive** for JSON/YAML, rather than literally "Sonar way". No custom profiles or rule overrides were applied. Exact profile records are in `baseline/quality-profiles.json`; scanner-used profiles are also recorded in the runtime log.

The baseline contains **84 issues: 10 vulnerabilities, 13 bugs and 61 code smells; zero security hotspots**. A fresh local server regenerates finding/component/profile keys and timestamps, plus compute-engine timing metadata. Compare findings by rule, component, line, message, type, severity and impacts, not generated keys.

## Findings by service

Severity columns are **BLOCKER / CRITICAL / MAJOR / MINOR / INFO**. Hotspots are **HIGH / MEDIUM / LOW**. Counts use SonarQube's legacy type/severity fields; newer impacts/software-quality fields are preserved raw.

| Deployable | Vulnerabilities | Bugs | Smells | Hotspots |
|---|---:|---:|---:|---:|
| api-gateway | 0/0/0/0/0 | 0/0/0/0/0 | 0 | 0/0/0 |
| auth-service | 0/0/0/0/0 | 0/0/0/0/0 | 0 | 0/0/0 |
| file-service | 0/0/0/0/0 | 0/0/0/0/0 | 0 | 0/0/0 |
| document-service | 1/2/0/0/0 | 0/0/1/0/0 | 0 | 0/0/0 |
| collab-service | 0/0/0/0/0 | 0/0/3/0/0 | 9 | 0/0/0 |
| notification-service | 0/0/0/0/0 | 0/0/0/0/0 | 0 | 0/0/0 |
| search-service | 0/2/0/0/0 | 0/0/0/0/0 | 0 | 0/0/0 |
| analytics-service | 0/0/0/0/0 | 0/0/0/0/0 | 0 | 0/0/0 |
| admin-service | 0/1/0/0/0 | 0/0/0/0/0 | 0 | 0/0/0 |
| audit-service | 0/0/0/0/0 | 0/0/0/0/0 | 0 | 0/0/0 |
| report-service | 0/0/0/0/0 | 0/0/3/0/0 | 0 | 0/0/0 |
| client-app | 0/0/2/1/0 | 0/1/3/0/0 | 19 | 0/0/0 |
| admin-dashboard | 1/0/0/0/0 | 0/2/0/0/0 | 33 | 0/0/0 |
| **Total** | **2/5/2/1/0** | **0/3/10/0/0** | **61** | **0/0/0** |

## Coverage and gaps

717 files were scanner-indexed; 427 file components were persisted by SonarQube. These are different measures: indexing or persistence does **not** prove semantic analysis. `baseline/scan-meta.json` contains per-file inventories, source/test classification, scanner-index details, languages, exclusions, and limitations.

| Deployable | Observed language coverage |
|---|---|
| api-gateway | Go sensor analyzed 24 files; Docker analyzed |
| auth-service | 32 Java files indexed, including 3 tests; Java sensor completed; Docker/XML/config files also processed |
| file-service | **9 Rust files indexed with no language; no Rust sensor executed.** Docker analyzed |
| document-service | 48 Python files indexed, including 15 tests; Python sensor completed; Docker analyzed |
| collab-service | 12 TypeScript files indexed, including 3 tests, plus JavaScript; JS/TS sensor completed |
| notification-service | Kotlin sensor reported **11/11 Kotlin sources**, Gradle **2/2**; 5 Kotlin tests indexed but not counted by that source sensor |
| search-service | 22 Python files indexed, including 7 tests; Python sensor completed; Docker analyzed |
| analytics-service | **33 Scala files had no Scala analyzer execution.** Docker/XML processed; nested scripts excluded |
| admin-service | **85 Ruby files had no Ruby analyzer execution.** Docker/config processing does not cover Ruby semantics |
| audit-service | **35 C# files indexed, including 4 tests, but C# semantic analysis explicitly refused the CLI scanner** |
| report-service | 56 Java files indexed, including 14 tests; Java sensor completed; Docker/XML processed |
| client-app | TypeScript/JavaScript, Java, XML, CSS/HTML and Docker sensors executed; detailed file classifications exported |
| admin-dashboard | 52 TypeScript files indexed, including 13 tests, plus JavaScript/CSS/HTML/Docker; corresponding sensors executed |

- **C#:** The scanner explicitly requires SonarScanner for .NET 5.x or higher. No .NET build was performed.
- **Rust, Ruby, Scala:** No corresponding language detection/profile/sensor execution appeared in this scan. Their indexed files are not semantically covered; text/secrets processing is not a substitute.
- **Kotlin:** Despite completion counts, DEBUG logs contain repeated `java.lang.NoSuchMethodError: 'java.lang.String com.intellij.openapi.fileTypes.FileType.getDefaultExtension()'`. Treat semantic precision as degraded; no application change was attempted.
- **Java:** Empty binaries directory used. The scanner warned about missing libraries/test binaries, unresolved imports/types and preview features.
- **Python:** Default compatibility range was 3.10–3.14.
- No tests were executed, coverage generated, dependencies installed, or SCA performed. Zero findings must not be interpreted as clean coverage of unsupported languages.
