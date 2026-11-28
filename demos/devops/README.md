# Local fleet fixtures

The six Helm releases use the platform app chart and a synthetic HTTP container.
The container exposes `/health` and `/work`; it does not implement the estate services.
Use Docker, kind 0.31, kubectl, Helm and Python 3 on the session machine.

```sh
demos/devops/kind/up.sh
demos/devops/kind/render.sh > /path/to/desired.yaml
demos/devops/kind/up.sh 1.35
demos/devops/kind/down.sh 1.35
demos/devops/kind/down.sh
```

The 1.34 cluster runs the observed releases and a local Metrics Server.
The 1.35 cluster starts with an empty namespace for server-side validation.
Use `kind-devops-20261128-1-34` or `kind-devops-20261128-1-35` explicitly
with kubectl, and work in `devops-fleet`.

## Read-only drift check

Run these commands at the repository root on Linux or in Windows PowerShell
with Python 3 and Helm 3 on PATH. The runner renders the six Deployment
manifests from the checked-out Helm chart and demo values, then compares them to
`fixtures/observed-deployments.json` (recorded local kind, not live AWS).
It needs no Bash, kubectl, running cluster, or AWS credentials.

```powershell
python -m pip install -r platform/standards/fleet/requirements.txt
python demos/devops/drift_check.py --markdown drift.md --json drift.json
```

The comparison checks container requests, limits, image, Deployment spec
replicas, and ownership labels. Exit codes: 0 = match, 1 = drift (red),
2 = input/tool error. In PowerShell, check `$LASTEXITCODE` after the runner.

For an API check, append the manifest
in `fixtures/legacy-api.yaml` to a full render and pass the combined file to
`fleet.py api --target 1.35`. The API catalog reports the actual removal version.

The alarm payloads, metric export and EKS inventory carry the label
`fixture: recorded, not live AWS`. The observed Deployment snapshot comes
from kind. Use the recorded add-on inventory for offline comparison only.

```sh
demos/devops/replay-alarm.sh "$DEVIN_WEBHOOK_URL" demos/devops/fixtures/alarm.json
demos/devops/replay-alarm.sh "$DEVIN_WEBHOOK_URL" demos/devops/fixtures/alarm-duplicate.json
demos/devops/replay-alarm.sh "$DEVIN_WEBHOOK_URL" demos/devops/fixtures/ok.json
```

Replay reads the bearer token from `DEVIN_WEBHOOK_BEARER` and sends every
supplied event, including duplicates. The receiver must enforce the ALARM filter
and deduplicate by alarm and transition time. An idempotency header travels
with each request; confirm receiver behavior in the automation history.
`fixtures/load-profile.json` supplies the same request profile for both phases
of the load check.
