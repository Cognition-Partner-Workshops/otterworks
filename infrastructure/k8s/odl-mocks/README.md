# ODL integration mocks

Run `scripts/odl/deploy-mocks.sh` from any directory with AWS/EKS access.
It preserves existing basic-auth Secrets and generates random credentials only
when absent. Consumers read the `username` and `password` keys in
`odl-mocks/{jira,pagerduty}-mock-basic-auth`; nginx uses the `auth` key.
Do not print these values or place them in shell command arguments/history.

The shared nginx ingress and wildcard default certificate serve:

- https://jira-odl.demo.otterworks.app
- https://pagerduty-odl.demo.otterworks.app

External-dns owns the individual DNS records. Services are ClusterIP only.
NetworkPolicies permit nginx access to both mocks and monitoring access to
PagerDuty. Only the Jira pods in `odl-mocks` can reach the Devin webhook
relay. The mock policies are not a tenant API access policy: consumers in another
namespace should use the authenticated public ingress.

Jira state is in memory. A sidecar searches unique labels and reconciles the
three ConfigMap stories every ten seconds, including after container/pod
restarts. The sidecar also ensures Jira has a webhook for created and updated
ENG issues with the `devin` label. It forwards through the ClusterIP service
`jira-devin-relay`, which adds the upstream authentication header and logs the
issue key and upstream status. For initial provisioning, supply
`DEVIN_JIRA_WEBHOOK_URL` and `DEVIN_JIRA_WEBHOOK_SECRET` via the deployment
script's environment. The script stores them in the `jira-devin-webhook`
Kubernetes Secret and preserves that Secret on subsequent runs.

PagerDuty SQLite uses **emptyDir**, so incidents and other changes are
lost and its built-in demo data **reseeds on pod restart**. Neither needs a PVC.

Images were built without changing the mocks repository at commit
`0fbc19b96a72611ecdb626b00bfc45efc5cd93f8`. Both images have that SHA tag and
`odl-1795112287` in the ECR repositories managed by
`infrastructure/terraform/odl`. Their Python base was pulled from
`mirror.gcr.io/library/python:3.12-slim` and retagged locally.

## Shared Alertmanager

No kube-prometheus-stack release values source was found under `demo-platform/`,
`infrastructure/`, or `platform/`. The overlay is
`observability/alertmanager/k8s/odl-routing-values.yaml`.

With Python 3 and PyYAML installed, run `python scripts/odl/route-alerts.py`.
It reads the current configuration only into memory, copies the existing Devin
URL into `monitoring/alertmanager-devin-webhook` (`url`), and preserves all
routes, Bofa configuration, webhook options, other receivers and Secret mounts.
It adds PagerDuty Events v2 to the same `devin-oncall` receiver, with the seeded
demo service's routing key held in `alertmanager-odl-pagerduty`. Both integrations
therefore receive `page="devin"` alerts without changing the routing tree.

The resulting configuration is stored in `alertmanager-odl-config`; the overlay
references that existing Secret rather than checking live URLs into Git. The
script prints only a structural redacted diff, then upgrades Helm release
`monitoring/prometheus` with `--reuse-values`, chart version **92.6.0**. Existing
credentials are never overwritten. Do not run `helm get values`, print Secret
objects/annotations, or commit live values/configuration exports: they contain
unrelated embedded credentials.

Local tests: `python -m unittest discover -s scripts/odl -p 'test_*.py' -v`.

For cleanup, first remove only the ODL PagerDuty integration from the live
receiver and safely reconcile the monitoring release; do not delete its mounted
Secrets while referenced. Then `kubectl delete namespace odl-mocks`. Destroy the
ECR stack only after all ODL image consumers have been removed, following its
README. Never destroy shared monitoring, ingress, or DNS infrastructure.
