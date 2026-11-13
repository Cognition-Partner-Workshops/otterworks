# admin-dashboard (frontend/admin-dashboard) runtime base image

Scanner: Trivy 0.71.0, vulnerability DB v2 updated 2026-11-13 12:56:33 UTC (`trivy-version.txt`).
Flags: `--scanners vuln --ignorefile /dev/null`, all severities, no suppressions.
Images were built locally from source; they are not the image deployed in ECR.

| Image | OS | Image ID | Findings |
|---|---|---|---|
| before (demo-ciso, `nginx-unprivileged:1.25-alpine`) | alpine 3.19.1 (end of life) | `sha256:0b708ae76df9fcbbbd37881a08d901743299b5b77d59a465771fba28c79f8833` | CRITICAL=3 HIGH=17 MEDIUM=43 LOW=27 total=90 |
| after (`1.30.6-alpine3.24@sha256:f5116ed4…` + `apk upgrade`) | alpine 3.24.2 | `sha256:98bc934adb179934e408c5c3e1e577dda9e78994a2c9d02504062a91df001318` | total=0 |

Alpine 3.19 is past end of support (Trivy reports `EOSL=true`), so the advisory feed no longer
tracks it and the "before" count of 90 understates its real exposure.

All image findings are OS packages; the runtime stage holds only nginx and the compiled bundle.

## Residual (not changed here): application packages

`trivy-fs-app-lockfile-residual.{txt,json}` scans `frontend/admin-dashboard/package-lock.json`:
CRITICAL=0 HIGH=17 MEDIUM=8 total=25, all in Angular 17.3.12 (`@angular/common`, `compiler`,
`core`, `router`). Angular 17 is out of support; every fixed version is in 19.2.x, 20.3.x or later,
so the fix is a two-to-three-major framework upgrade, which is out of scope for an image change.
These packages are compiled into the static bundle, so the image scan cannot see them.
