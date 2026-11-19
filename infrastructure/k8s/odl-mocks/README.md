# ODL integration mocks

Run `scripts/odl/deploy-mocks.sh` from any directory with AWS/EKS access.
It preserves existing basic-auth Secrets and generates random credentials only
when absent. Consumers read the `username` and `password` keys in
`odl-mocks/{jira,pagerduty,confluence}-mock-basic-auth`; nginx uses the `auth` key.
Do not print these values or place them in shell command arguments/history.

Use `scripts/odl/deploy-mocks.sh --only confluence` when updating Confluence
independently. This requires the existing namespace, reads/creates only the
Confluence credential Secret, and applies only Confluence-labeled resources.
It never reads or reapplies the Jira Secret or redeploys Jira. All credential
creation uses create-if-absent, never an update or apply of an existing Secret.

The shared nginx ingress and wildcard default certificate serve:

- https://jira-odl.demo.otterworks.app
- https://pagerduty-odl.demo.otterworks.app
- https://confluence-odl.demo.otterworks.app/wiki

Confluence natively serves `/wiki`, `/wiki/api/v2` and `/wiki/rest/api`;
the ingress preserves these paths without a rewrite and also authenticates
the app's `/static` assets. `/wiki` redirects to the built-in OPS landing page
(use `curl -L` to follow it). SQLite uses emptyDir and
retains the built-in OPS and ENG spaces. A sidecar reconciles two ENG pages by
exact title every ten seconds through the v2 API, restoring them after pod
replacement without duplicating existing pages. The pages summarize
`.agents/skills/rest-conventions/SKILL.md` and reserve customer source mapping.
No VPC CNI or cluster-wide enforcement settings are changed; the existing
cluster currently does not enforce these NetworkPolicies.

External-dns owns the individual DNS records. Services are ClusterIP only.
NetworkPolicies declare nginx access to all three mocks and monitoring access to
PagerDuty. They are not a tenant API access policy: consumers in another
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

The relay forwards labelled creations and updates that add the label. The Jira
mock omits changelogs, so the relay tracks previously seen labels in the
`jira-devin-relay-label-state` ConfigMap and logs skipped events with their
reason. Because Jira's filter excludes unlabelled updates, a label removal
cannot reset this fallback state unless the relay receives an unlabelled event.

PagerDuty SQLite uses **emptyDir**, so incidents and other changes are
lost and its built-in demo data **reseeds on pod restart**. None needs a PVC.

Images were built without changing the mocks repository at commit
`0fbc19b96a72611ecdb626b00bfc45efc5cd93f8`. All three images have that SHA tag and
`odl-1795112287` in the ECR repositories managed by
`infrastructure/terraform/odl`. Jira and PagerDuty's Python base was pulled from
`mirror.gcr.io/library/python:3.12-slim` and retagged locally; Confluence's
Dockerfile uses that mirror directly.

## Shared Alertmanager

The mock NetworkPolicies allow ingress only from `ingress-nginx` and
`monitoring`; seed sidecars use localhost within their mock pod, not the Service.
Apply policy-only updates with `kubectl apply -f
infrastructure/k8s/odl-mocks/networkpolicy.yaml`. The relay policy separately
permits only Jira pods in `odl-mocks` to reach
`jira-devin-relay:8080`; no other same-namespace allowance is needed. The relay
forwards incoming webhooks to its HTTPS upstream and does not call mock Services.

These policies are declared but the shared cluster's VPC CNI runs with
`--enable-network-policy=false`. Until enforcement is enabled, in-cluster
callers can reach the mock Services without basic auth, which is enforced only
at ingress. The mocks hold only synthetic demo data. This deployment does not
change cluster-wide enforcement.

No kube-prometheus-stack release values source was found under `demo-platform/`,
`infrastructure/`, or `platform/`. The overlay is
`observability/alertmanager/k8s/odl-routing-values.yaml`.

With Python 3 and PyYAML installed, run `python scripts/odl/route-alerts.py`.
It reads the current configuration only into memory, copies the existing Devin
URL into `monitoring/alertmanager-devin-webhook` (`url`), and preserves all
routes, existing configuration, webhook options, other receivers and Secret mounts.
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
