# Alert webhook credential

The standalone deployment synchronizes the admin Helm release's persisted
`ALERT_WEBHOOK_SECRET` to Grafana with
`scripts/sync-grafana-webhook-secret.sh`. It copies **only** that key into a Secret
in the monitoring namespace, sets the Grafana container's environment from that
Secret, and restarts Grafana so provisioning reloads the contact-point credential.
The value is never printed or passed on a command line. Helm upgrades retain the
source secret; changing it and re-running the helper also rotates the consumer.

The defaults are admin namespace `otterworks`, source `admin-service-secrets`,
Grafana namespace `monitoring`, and a uniquely discovered deployment labelled
`app.kubernetes.io/name=grafana`. Override `ADMIN_NAMESPACE`, `ADMIN_SECRET`,
`GRAFANA_NAMESPACE`, `GRAFANA_DEPLOYMENT`, `GRAFANA_CONTAINER`, or `GRAFANA_SECRET`
for a different installation. A missing source credential fails closed.
An absent monitoring namespace or an empty Grafana deployment list skips sync
successfully. Namespace discovery uses `--ignore-not-found`; authorization,
connectivity, and other Kubernetes API errors still fail the deployment.

Run the helper only for the admin endpoint targeted by that Grafana contact
point. Per-tenant deploys intentionally do not rewrite shared platform monitoring.
Local Compose already passes the same `ALERT_WEBHOOK_SECRET` environment setting
to both services; export one value before starting/recreating them to override
the local-only demonstration default.
