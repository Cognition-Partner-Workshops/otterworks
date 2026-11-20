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

With Python 3 and PyYAML installed, inject `DEVIN_ALERT_WEBHOOK_URL` and
`DEVIN_ALERT_WEBHOOK_SECRET` through the execution environment, then run
`python scripts/odl/route-alerts.py`. Both values, including the URL, are sensitive:
never print them, put them in command arguments or files, or record them in a
transcript. The script creates/updates only the dedicated
`monitoring/alertmanager-odl-devin-webhook` credential Secret (`url`, `secret`),
labeled `run_token=odl-1795112287`. Later runs can reuse that Secret with neither
variable supplied; supplying both rotates its credentials without changing other
Secrets. Partial credentials are rejected.

The script inserts `odl-devin-oncall` immediately before `devin-oncall`, matching
both `page="devin"` and `namespace="otterworks-odl"`. ODL recording rules retain
`namespace` through their aggregations, so critical alerts inherit it; they do
not emit `tenant="odl"`. The receiver uses `url_file` and the
`X-Webhook-Secret` header via `http_config.http_headers` / `files`, supported and
parser-checked on live Alertmanager **v0.34.1**. The Secret is mounted through
`alertmanagerSpec.secrets`; neither value is embedded in Alertmanager YAML.

The receiver also copies the existing ODL PagerDuty Events v2 configuration,
using `alertmanager-odl-pagerduty`. The webhook receives firing notifications only
(`send_resolved: false`); PagerDuty receives firing and resolved notifications
(`send_resolved: true`). Rerunning the script corrects the former webhook
`send_resolved: true` setting without changing other receiver options.
Every existing route/receiver and unrelated Secret mount is
preserved: t-main and incident paging stay on `devin-oncall`. The new route
inherits grouping intervals and copies the existing on-call `group_wait`, so
resolution delivery can take the inherited group interval (currently five minutes).

The resulting configuration is stored in `alertmanager-odl-config`; the overlay
references that existing Secret rather than checking live URLs into Git. The
script prints a structural redacted diff, then upgrades Helm release
`monitoring/prometheus` with `--reuse-values`, chart version **92.6.0**. Existing
unrelated credentials are never overwritten. Do not run `helm get values`, print Secret
objects/annotations, or commit live values/configuration exports: they contain
unrelated embedded credentials.

Local tests: `python -m unittest discover -s scripts/odl -p 'test_*.py' -v`.

## ODL read-latency incident (ODL-09)

Requires Python 3 (standard library only), `kubectl`, Linux `setsid`/`/proc`,
and cluster credentials authorized to read the tenant JWT Secret and execute
read-only monitoring queries from the runtime pod. Reset also requires reading
the tenant Mongo Secret and dropping the three incident read indexes. Only **t-odl**, namespace
`otterworks-odl`, and scenario **odl-read-latency** are accepted; tenant/URL
overrides are deliberately unavailable.

```sh
scripts/odl/scenario.sh status odl-read-latency
scripts/odl/scenario.sh reset odl-read-latency     # replay only: remove responder read indexes
scripts/odl/scenario.sh arm odl-read-latency       # bounded 1800-second default
scripts/odl/scenario.sh status odl-read-latency
scripts/odl/scenario.sh disarm odl-read-latency    # ALWAYS run after the demo
```

Arm reads the tenant's JWT signing key into memory, signs an expiring bearer
token, and fetches real source keys from an authenticated customer-list read.
Detached load then cycles Db2, Oracle and CRM key filters through
`https://api-t-odl.demo.otterworks.app/api/v1/odl/customers`, with **6 offered
requests/second and at most 16 in flight**. Saturated dispatches are shed rather
than queued; redirects cannot forward the token to another host. Tokens,
credentials, response bodies and customer keys are not logged. PID identity,
start time and process group are checked before disarm; SIGTERM stops dispatch
and drains outstanding requests. PID/readiness/log files live in gitignored
`scripts/odl/.state/`. Logs contain numeric summaries only. Natural expiry also
drains; disarm afterward cleans the stale PID. Do not delete state while armed.

Arm/disarm are **load-only**: no indexes, predicates, Mongo data, API configuration,
resources, alert thresholds or alert hold times are changed. Disarm stops load
only; there is nothing else to restore. Status prints load identity, recorded
p95/p99, completed request rate and both latency alert states. With no traffic,
quantiles may be `NaN`/no-data; that is not a passing latency measurement.

The unchanged critical rule requires p99 >2s and >1 completed request/second
for **10m**, using a 5m rate window. Allow approximately **12–15 minutes** for
the rate ramp, hold and delivery. `ODLReadLatencyHigh` is the non-paging p95
warning. Critical alerts retain `namespace="otterworks-odl", page="devin"`
and route to **odl-devin-oncall**, which delivers firing notifications to the
new Devin automation and firing/resolved events to PagerDuty. Stopping load
clears the rate gate after the window decays; allow the inherited grouping
interval for PagerDuty's resolved delivery.

### Calibration and before/after gate

Initial calibration used a **150-second** burst; the full 10-minute hold
was intentionally not exercised during calibration. At the defaults, that burst completed **601
HTTP 200s**, shed 299 dispatches, and drained in **151.9s**. A direct histogram
query over the burst window measured **3.66 requests/s, p95 9.23s, p99 10s**
(p99 reaches the top finite histogram bucket, so is not an exact tail timing).
Both latency alerts were pending, not firing; the webhook notification counter
was unchanged. Wait at least **five quiet minutes after draining between any
calibration bursts**, start only with inactive alerts, and verify no firing
latency alerts or new webhook notifications after each burst. Never use repeated
short bursts to accumulate the 10-minute hold.

Before gate: sustain the normal demo load, verify >1 completed request/s and
p99 >2s, then observe `ODLReadLatencyCritical` fire and its real notification.
After gate: deploy the responder's code fix and rerun **the same** load; require
>1 completed request/s, p99 staying below 2s (and p95 below 0.5s), with the
critical/warning alerts inactive after their windows clear. An idle/NaN graph,
reduced offered load, changed resources or shortened alert hold does not pass.
**Always disarm after either gate.**

### Reset for replay

After disarming and draining **all** load generators, run `reset odl-read-latency`
before replaying the before gate. Reset refuses while a scenario worker is alive
on this VM, including workers launched from another checkout. Workers on another
machine cannot be detected through local PID state: stop those on their originating
machine first. Do not start load concurrently with reset from another checkout.

Reset authenticates using `otterworks-odl/operational-data-layer-mongo` Secret
credentials in memory/stdin, never argv or logs. It removes only non-unique,
non-partial compound indexes with exactly `(source_keys.db2_cust_no, _id)`,
`(source_keys.oracle_account_ids, _id)` or `(source_keys.crm_contact_id, _id)`,
both fields ascending. Selection uses key patterns and options, not names;
partial, unique, sparse, custom-collation and all other indexes are preserved.
Absent indexes are a no-op; ambiguous duplicate patterns are refused before any
drop. The command prints the indexes before, what it dropped, and the observed
after-state. It changes no documents, images, rules, monitoring or automation.

If responder code such as PR #3319 is deployed, API startup can recreate these
indexes. Reset does not disable that code or promise they will stay absent;
inspect its after-state and deploy the approved pre-incident image separately if
needed. Reset also does not undo a predicate-based code fix. Do not reset between
the before and after gates: that would invalidate verification of the fix.

### Frontend monitoring scope

The static Nginx web-app has no Prometheus endpoint: `/metrics` returns the SPA
HTML. The `odl/web-app.yaml` and `odl-before/web-app.yaml` overlays under
`infrastructure/helm/tenant-values/` disable only these tenants' web-app
ServiceMonitors. `scripts/odl/deploy-odl.sh` calls `scripts/deploy-tenant.sh`, which
automatically passes the matching tenant overlay to Helm. `cd-tenant.yml` already
defers this repository's `demo-odl` deployments to that wrapper; the generic
tenant deploy path also loads these overlays. Redeploying either tenant therefore
keeps the monitor off without changing chart defaults, main, or other tenants.
The operational-data-layer API's real `/metrics` scrape remains enabled.

The durable responder fix belongs in
`services/operational-data-layer/odl_sync/api.py`: make the source-key query
predicates match the existing partial-index conditions (string type for Db2/CRM;
array-element existence for Oracle), with real-Mongo plan regression coverage.
The scenario harness deliberately does not implement or deploy that fix.

For cleanup, first remove only the dedicated ODL route/receiver and safely
reconcile the monitoring release; do not delete its mounted
Secrets while referenced. Also remove the original mock PagerDuty integration
from `devin-oncall` before deleting the mocks namespace, preserving its webhook.
Then `kubectl delete namespace odl-mocks`. Destroy the
ECR stack only after all ODL image consumers have been removed, following its
README. Never destroy shared monitoring, ingress, or DNS infrastructure.
