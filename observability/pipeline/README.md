# Pipeline monitoring commands

From the repository root, with the existing named Snowflake connection and key in
`~/.snowflake/` (mode 600):

```sh
make warehouse/snowflake/.venv/.sfx-installed
make sfx-operate-load
make sfx-operate-check
make sfx-operate-alert
make sfx-operate-break
make sfx-operate-alert
make sfx-operate-exporter
# Or:
warehouse/snowflake/.venv/bin/python observability/pipeline/sfx_pipeline_exporter.py --port 9471 --interval 30
curl http://localhost:9471/metrics
make sfx-operate-reset
make sfx-operate-alert
warehouse/snowflake/.venv/bin/python -m pytest warehouse/pipeline/test_pipeline.py -q
```

## Configuration

Checks, alerts and exporter accept the same flags:

| Environment | Flag | Default |
|---|---|---|
| SFX_ROW_DROP_THRESHOLD | --row-drop | 0.05 |
| SFX_NULL_RATIO_THRESHOLD | --null-ratio | 0.01 |
| SFX_LOAD_ERROR_THRESHOLD | --load-errors | 0 |
| SFX_LOOKBACK_HOURS | --lookback-hours | 24 |
| SFX_EXPORTER_PORT | --port (exporter) | 9471 |
| SFX_REFRESH_SECONDS | --interval (exporter) | 30 |

Ratio thresholds are fractions, firing strictly above the threshold. Any COPY
status other than Loaded always fires regardless of the error-count threshold.
Lookback accepts 1–336 hours (COPY_HISTORY retention). No previous pipeline day
means no row-drop comparison; an empty feed set returns zero values and no firing
checks. No new data-freshness check is included.

All checks use SFX_D1110_OPS_WH with step=monitor. Daily view metrics join to raw
records scoped by `_SRC_FILE LIKE 'pipeline/%'`. For COPY history, only the newest
attempt for each currently retained pipeline stage file is evaluated. This lets a
successful replay supersede a failure and reset's staged-file removal retire the
break without waiting for historical COPY records to expire. A wholly failed COPY
still fires while its staged file remains, even when no raw records were loaded.
Do not remove a failed staged file unless deliberately retiring/resetting that feed.

Exporter failure sets last_scrape_success=0, retains the last data gauges, and
prints a generic error without connection details. Grafana expressions gate check
metrics on successful refresh, avoiding treating stale values as current.

## Grafana and Prometheus

Run the host exporter before `docker compose -f docker-compose.infra.yml up -d prometheus grafana`.
Prometheus scrapes host.docker.internal:9471; the Compose host-gateway mapping
supports Linux. If the exporter port changes, update the scrape target too.
The host exporter reads local credentials; no credentials are baked into containers.

Set DEVIN_PIPELINE_WEBHOOK_URL and DEVIN_PIPELINE_WEBHOOK_SECRET in the environment
before starting Grafana. Compose passes them through; provisioning interpolates
them into the POST webhook contact point's URL and Bearer credentials. Use a valid
URL when enabling this contact point; blank URL is intended for direct-script
dry runs, not an enabled Grafana webhook receiver.

Rules use datasource UID Prometheus and shared check_firing gauges (one rule per
check). The existing org-1 Default notification tree remains the root; its child
route matches pipeline=sfx-d1110 and groups those alerts by pipeline. Grafana
provisions the entire notification-policy tree, not independent additive trees.
Loki is not deployed or provisioned in this Compose stack; no Loki rule is added.

## Direct notification behavior and JSON

With DEVIN_PIPELINE_WEBHOOK_URL unset/empty, fire_alert.py prints JSON and exits 0.
With a URL and firing checks, it requires DEVIN_PIPELINE_WEBHOOK_SECRET and sends
Authorization: Bearer via POST, exiting 0 for 2xx and nonzero for HTTP/transport
failure. No response body, URL, or secret is logged. With all checks green it prints
a resolved payload with an empty alerts array and does not POST (even with URL set).
Only firing checks are included in alerts. startsAt is evaluation time; fingerprints
are stable SHA-256 label hashes, not persistent incident start times.

Full example with one firing check follows; each additional firing check adds the
same alert object shape with its own labels, annotations, values and fingerprint.
Grafana's native notification may include additional optional fields.

```json
{
  "receiver": "devin-pipeline-webhook",
  "status": "firing",
  "orgId": 1,
  "alerts": [
    {
      "status": "firing",
      "labels": {
        "run": "sfx-d1110",
        "model": "stg_billing__usage_daily",
        "severity": "critical",
        "pipeline": "sfx-d1110",
        "team": "otterworks",
        "alertname": "SfxPipeline_load_failure",
        "check": "load_failure"
      },
      "annotations": {
        "summary": "Pipeline load_failure firing",
        "description": "day=2026-11-10 file=pipeline/2026-11-10.csv value=6 threshold=0"
      },
      "values": {
        "A": 6,
        "threshold": 0
      },
      "startsAt": "2026-11-10T22:23:00Z",
      "endsAt": "0001-01-01T00:00:00Z",
      "generatorURL": "",
      "fingerprint": "2e330ca579210e00"
    }
  ],
  "groupLabels": {
    "pipeline": "sfx-d1110"
  },
  "commonLabels": {
    "run": "sfx-d1110",
    "model": "stg_billing__usage_daily",
    "severity": "critical",
    "pipeline": "sfx-d1110",
    "team": "otterworks"
  },
  "commonAnnotations": {},
  "externalURL": "http://localhost:3001/",
  "version": "1",
  "groupKey": "{}:{pipeline=\"sfx-d1110\"}",
  "truncatedAlerts": 0,
  "title": "1 pipeline checks firing",
  "state": "alerting",
  "message": "1 pipeline checks firing"
}
```
