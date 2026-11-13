# web-app (frontend/client-app) runtime base image

Scanner: Trivy 0.71.0, vulnerability DB v2 updated 2026-11-13 12:56:33 UTC (`trivy-version.txt`).
Flags: `--scanners vuln --ignorefile /dev/null`, all severities, no suppressions.
Images were built locally from source; they are not the image deployed in ECR.

| Image | OS | Image ID | Findings |
|---|---|---|---|
| before (demo-ciso, `nginx-unprivileged:1.27-alpine`) | alpine 3.21.3 | `sha256:2e5bb0d521c1cce768b624e0321163bba62491111b1abc4594c8039cbcfe2a29` | CRITICAL=3 HIGH=65 MEDIUM=103 LOW=46 total=217 |
| after (`1.30.6-alpine3.24@sha256:f5116ed4…` + `apk upgrade`) | alpine 3.24.2 | `sha256:c0817bf16024c6c9de3913ac51d06423569f5363ee343a0d12471da8ac7c6c76` | total=0 |

All 217 findings are OS packages. Trivy finds no language packages in the image:
the runtime stage contains only nginx and the compiled static bundle (no `node_modules`
or lockfile), so bundled JavaScript dependencies are not visible to an image scan.

Files: `trivy-{baseline,after}.txt` (scanner table output), `trivy-{baseline,after}.json`
(scanner JSON reduced to ID/package/version/fix/severity), `summary.txt`, `reproduce.sh`
(the script that produced these files; paths point at local worktrees of demo-ciso and this branch).
