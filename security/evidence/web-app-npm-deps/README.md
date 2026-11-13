# web-app (frontend/client-app) npm dependencies

Scanner: Trivy 0.71.0, vulnerability DB v2 updated 2026-11-13 12:56:33 UTC (`trivy-version.txt`).
Flags: `--scanners vuln --ignorefile /dev/null`, all severities, no suppressions.

| Scan | Findings |
|---|---|
| `trivy fs frontend/client-app/package-lock.json`, demo-ciso | CRITICAL=2 HIGH=19 MEDIUM=11 LOW=2 total=34 |
| same, this branch | MEDIUM=1 total=1 |
| `trivy image` of this branch's web-app build | 217 (unchanged; all OS packages from the base image) |

The image scan does not change because the runtime image ships only the compiled bundle, which
Trivy cannot attribute to npm packages; the lockfile scan is the measurement for this fix.
The OS findings are handled by the separate runtime base image change.

Residual: `@tiptap/core` 2.27.2 GHSA-cp6q-959q-f8rh (MEDIUM), fixed only in 3.30.4; tiptap 3 is
a major upgrade of the editor stack and is not included.

Files: `trivy-fs-{baseline,after}.{txt,json}`, `trivy-npm-after.{txt,json}` (image scan),
`summary.txt`, `reproduce.sh`.
