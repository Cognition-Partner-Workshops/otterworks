# CISO answer key (builder only; goes to estate-keys/ciso)
## Owners map (PR 2851)
security/owners.yaml lists 15/16 services; notification-service absent. notification-service ships commons-text 1.9 (build.gradle.kts:24). owners.missing(services)==['notification-service'].
## Checkov (PR 2852)
modules/database/main.tf aws_db_instance.postgres: CKV_AWS_16 storage_encrypted=false (:61), CKV_AWS_17 publicly_accessible=true (:69). Checkov 3.4.5 failed 170->172. Encryption fix forces replacement.
## Stale ignore + Trivy base (PR 2853)
.trivyignore:48 CVE-2024-6119, no reason, no exp, filed under Debian section; masks 2 HIGH on api-gateway. services/api-gateway/Dockerfile:10 alpine:3.19 -> alpine:3.18.0; Trivy OS before C0/H2, after C3/H6 (busybox CVE-2022-48174 CRITICAL; libssl CVE-2023-5363, CVE-2024-6119; musl CVE-2025-26519).
## Policy drift (live, t-ciso, ns otterworks-ciso)
allow-namespace-egress edited live: appended egress `to: ipBlock 0.0.0.0/0` (no ports). allow-dns and default-deny-all match git. Tenant expires 2026-11-16T13:34:30Z, run_token ciso-20261113, teardown scripts/teardown-tenant.sh ciso.

## SARIF exports

The exports at `/home/ubuntu/prompts/ciso/sarif/` passed SARIF 2.1.0 schema validation and remain outside git.

- `sonarqube.sarif` contains 188 results from a local SonarQube scan of commit `e65bd28db3f9fac4b75bd254b875cec393f4eddb`, converted with `security/ingest/sonar_sarif.py`. All seven inert rows from `security/ingest/fixtures/inert-noise.json` remain: three cross-scanner duplicates (SQL injection, weak share-token hashing, trusted identity header), three false positives (test password, mock token, generated Gradle file), and one unreachable offline migration finding. Eight additional exact-fingerprint duplicate rows remain. The exporter excluded 91 non-security code-smell rows by design; the CLI scanner could not analyze C# without SonarScanner for .NET.
- `cluster.sarif` contains 126 native Trivy 0.76.2 results from 26 live manifest objects read from `otterworks-ciso`. Repeated rule findings across workloads remain, with no exact duplicate rows or added synthetic noise. The input includes the live NetworkPolicy drift, but Trivy did not flag the drift.

The SARIF files exclude the fixture's `seeded_as` and `why` answer-key fields. Cluster access was read-only, and the local SonarQube containers were removed after export.
