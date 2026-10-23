# Replatform chart

This generic Helm chart packages the shared deployment surface of the existing service charts: Deployment, ClusterIP Service, optional Ingress, NetworkPolicy, IRSA-capable ServiceAccount, optional ConfigMap and Secret, and optional ServiceMonitor and PrometheusRule. It creates no AWS resources. All rendered resources, including the Deployment pod template, carry the disposition and run-token labels plus expiry and evidence annotations.

The portfolio disposition standard says: **“Replatform needs a managed target for each stateful dependency and a named upgrade path for anything past end of life.”** Document those target and upgrade decisions in `dispositionEvidence`.

## Required values

| Value | Purpose |
|---|---|
| `runToken` | Required value matching `<prefix>-YYYYMMDD-xx`. |
| `expires` | Required RFC 3339 timestamp stored as an annotation. |
| `dispositionEvidence` | Required assessment row or evidence reference. |
| `image.repository`, `image.tag` | Required container image. |

`service.type` must be `ClusterIP`; the shared ingress-nginx controller owns the only permitted LoadBalancer Service. Defaults are one replica, port 8080, small requests/limits, enabled NetworkPolicy, and disabled Ingress/monitoring.

## Configuration

Set `env` and `envFrom` for workload environment settings. Non-empty `config` and `secrets` maps create resources and are automatically referenced from the Deployment. `healthCheck` configures HTTP liveness/readiness probes. Set `serviceAccount.roleArn` to add the IRSA annotation. `ingress` configures ingress-nginx routes and `monitoring` controls the ServiceMonitor and optional PrometheusRule.

Render or validate without applying:

```sh
helm lint infrastructure/dispositions/replatform --strict \
  -f infrastructure/dispositions/replatform/ci/values-ci.yaml
helm template sample infrastructure/dispositions/replatform \
  -f infrastructure/dispositions/replatform/ci/values-ci.yaml
```

Use the rendered chart through the target cluster's existing deployment pipeline. CI only lints and renders; it never installs or upgrades a release.
