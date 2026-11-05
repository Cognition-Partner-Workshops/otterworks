# Runbook: KYC Document Upload Latency

**Severity:** Critical (page) / Warning (channel only)

## Alert

Objective: 99% of KYC document uploads finish in under 2 seconds, measured over 30 days.

- `KycDocumentUploadLatencyPage`: upload p99 over 5m > 2s for 10m; `team=platform`, `severity=critical`, platform on-call rotation.
- `KycDocumentUploadLatencyWarning`: upload p99 over 5m > 1.5s for 15m; `team=platform`, `severity=warning`, platform channel only (no page).
- Both use `job:kyc_document_upload_duration_seconds:p99_5m`, aggregating all statuses/instances for `job="kyc-docs"`, `application="kyc-docs"`, `method="POST"`, `uri="/documents/{customer}"`. GET/list traffic is excluded. These short-window alerts are not the 30-day SLO calculation.

## Impact

Onboarding identity documents are taking too long to arrive. Clients may time out or retry, creating duplicate files. Check failed requests as well as latency: a fast rejection is not a successful upload.

## What to Check First

1. Check `up{job="kyc-docs"}` and the **KYC document upload latency (p99)** panel in Service Detail. No samples or no traffic is not proof of healthy latency. Prometheus must share the stand-in's `wave1-vm_default` network to reach `kyc-01:8443`. The self-signed stand-in scrape uses HTTPS with verification disabled; do not copy this TLS exception to production.
2. Compare `rate(http_server_requests_seconds_count{job="kyc-docs",method="POST",uri="/documents/{customer}"}[5m])` by `status`, `outcome`, and `instance`. Check traffic changes, errors, and recent releases. GET the health endpoint at `https://kyc-01:8443/actuator/health` from the same network.
3. Review `/var/log/kyc/kyc-docs.log` for I/O errors and the `stored ... (... bytes)` completion messages. They include customer identifiers: use restricted access, redact evidence, and do not copy identities or document bodies into incident channels.
4. Check free space/inodes, disk latency, and I/O wait on the filesystem backing `/var/kyc/uploads` (for example `df -h /var/kyc/uploads`, `df -i /var/kyc/uploads`, `iostat -xz 1`). Include the JVM multipart temporary filesystem. Node disk metrics are not currently scraped by this stand-in; use host tools rather than assuming a storage histogram exists.

## Slow Storage or Slow Client?

- The Spring HTTP timer includes multipart body reading/resolution before the controller. Large files (configured maximum file size 10MB; the servlet also enforces its request-size limit) and slow branch links can increase total time even when saving is fast. Compare request sizes and affected branches/clients using restricted ingress/client timing evidence; branch/client identifiers are not metric labels and must not be added as high-cardinality labels.
- Storage is local disk, **not S3**. `DocumentStore.save` makes directories and calls `Files.copy` into `/var/kyc/uploads/<customer>/`. Broad slowdowns across clients with high disk await/utilization, I/O wait, low space/inodes, or copy failures point toward storage (including multipart spooling).
- Concentration at one branch/client or on large bodies, with healthy disk and normal small synthetic uploads, points toward client/network/body-read latency. Compare total request/body transfer time with server-side copy time using an approved profiler or controlled reproduction. There is no existing `Files.copy` latency metric or tracing instrumentation in this app; a completion log proves completion, not how long the copy took. Do not claim that total request latency isolates storage time.
- For controlled checks, use synthetic files only and compare equal-sized uploads from an affected branch and near the server. Do not log request bodies or real KYC documents.

## Mitigation

- For disk contention, stop nonessential competing I/O or move scheduled backup work with the storage owner's approval. Restore capacity or expand the volume if full; never delete compliance documents to free space.
- For a slow branch link, engage the network team and reduce concurrent retries/offer an approved alternate intake path. Do not raise the 10MB limit or retry indefinitely as a latency fix.
- Roll back a correlated application/configuration change through the normal release process if safe. Keep existing alert thresholds intact. Verify p99 and error rates recover under representative traffic; no-traffic NaN is not recovery.

## SLO and Escalation

For the 30-day latency fraction, divide `sum(increase(http_server_requests_seconds_bucket{job="kyc-docs",application="kyc-docs",method="POST",uri="/documents/{customer}",le="2.0"}[30d]))` by the same sum with `le="+Inf"`. Target >= 0.99; retain at least 30 days of data and interpret low/zero traffic explicitly. Histogram buckets include the boundary (<=2s), approximating the stated under-2s objective. Track failures separately.

Critical routes to `platform-oncall`; warning routes to `platform-channel` (#platform) and never to the pager receiver. Configure `PLATFORM_ONCALL_WEBHOOK_URL` on Alertmanager to the platform rotation's Alertmanager-compatible webhook and `PLATFORM_SLACK_WEBHOOK_URL` to a webhook permitted to post in #platform (modern Slack webhooks may be channel-bound). Pass both into the Alertmanager container environment; the existing incident Compose file does not forward these new variables automatically. Defaults are local demo sinks, **not a live pager**. Validate delivery before relying on paging. Restart Alertmanager after changing these environment variables.

Escalate critical incidents to platform on-call; involve the host/storage owner for I/O pressure and the branch network owner for client concentration. Provide redacted timestamps, p99/volume/error trends, size distribution, affected scope, disk evidence, and recent changes. Involve the compliance owner before any action affecting document retention or alternate intake.
