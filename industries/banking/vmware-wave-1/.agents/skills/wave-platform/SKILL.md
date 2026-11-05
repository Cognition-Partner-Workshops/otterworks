---
name: wave-platform
description: Local VM stand-ins, platform gate and parity commands for the wave applications.
---

# Wave mechanics

Read the host configuration and stand-in files for each application under `industries/banking/vmware-wave-1/` before assessing its runtime dependencies. Exclude `demos/` from assessment and application-worker scope.

Set a unique `COMPOSE_PROJECT_NAME` before `make vm-build`, `make vm-up`, `make vm-rates` or `make reset`. `make vm-smoke` checks one endpoint per application. `make reset` drops the selected Compose project's volumes. Do not call `ecr`, `ns` or any cloud deploy target in a local-only run.

Pin both the reusable workflow and platform standard to the identical immutable commit in `.github/workflows/bank-wave1.yml`. Its `standards_ref` is the same commit as the reusable workflow reference. Application pipelines load `platform/standards/` at that pin. Keep `eks_deploy` false for local-only runs.

Gate results use rule families BASE, SECRET, SEC, RES, PROBE, LABEL, REG and NET. Read the full result table and retain each failed rule and rerun. Configure Helm through `platform/standards/helm/app/values.yaml` and use secret references in `secretEnv`.

Compare each application with the commands in `parity/README.md`. Keep independent VM and kind endpoints, the same input rows and business days, and the JSON report with its depth table. Unit tests and status-only smoke checks cover narrower checks than body and batch parity. Missing endpoints and failed depths stay red.
