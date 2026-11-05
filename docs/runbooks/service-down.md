# Runbook: ServiceDown

**Severity:** critical · **Rule file:** `observability/prometheus/alerts.yml` (group `otterworks.service.availability`)

> **Does this page?** Not on its own. The rule has no `page` label, so
> Alertmanager (`observability/alertmanager/alertmanager.yml.tmpl`) sends it to
> the default `sink` receiver only. Only `page: devin` rules
> (`observability/prometheus/incident_alerts.yml`) reach the Devin webhook and
> `#otterworks-alerts`. If you are looking at this at night, either someone
> forwarded it or a paging alert on the same service fired alongside it. Check
> both.

## What it means

Prometheus could not scrape `/metrics` on one target (`job`, `instance` labels)
for four evaluations in a row. Either the process is not running, it is running
but not listening, or it is so busy it misses the 10 s scrape timeout. Requests
that the API gateway routes to that service fail with 502/503 until it is back.

## Threshold and why

`up == 0` for `1m`. Prometheus scrapes every 15 s (`prometheus.yml`), so one
minute is four failed scrapes in a row. A single failed scrape or a normal
rolling restart (a few seconds) does not fire. A crash loop or a dead container
does.

## First three things to check

1. **Which target, and is it only one?**
   ```bash
   curl -s "$PROM/api/v1/query" --data-urlencode 'query=up == 0' | jq -r '.data.result[] | "\(.metric.job // .metric.instance // .metric.queue_name // .metric.table_name) \(.value[1])"'
   ```
   If many jobs are down at once, the problem is Prometheus's network or the
   node, not the services. Check `up{job="prometheus"}` and the node before
   you look at any one service. Grafana **OtterWorks Overview**
   (`/d/otterworks-overview`), panels *Service Health Grid* and *Services Down*.
2. **Is the process alive, and why did it stop?**
   ```bash
   # Compose
   docker ps -a --filter name=otterworks-<service> --format '{{.Names}} {{.Status}}'
   docker logs --tail 100 otterworks-<service>
   # EKS
   kubectl -n otterworks-<tenant> get pods -l app.kubernetes.io/name=<service>
   kubectl -n otterworks-<tenant> describe pod -l app.kubernetes.io/name=<service> | sed -n '/Last State/,/Events/p'
   kubectl -n otterworks-<tenant> logs -l app.kubernetes.io/name=<service> --previous --tail 100
   ```
   `OOMKilled` goes to [high-memory](high-memory.md). `CrashLoopBackOff` with a
   config or secret error means a bad deploy or a missing secret.
   `ImagePullBackOff` means a bad image tag.
3. **Does it answer its health check from inside the network?**
   ```bash
   curl -sf -m 5 http://localhost:<port>/health || echo unhealthy   # Compose, host port from docker-compose.yml
   kubectl -n otterworks-<tenant> exec deploy/api-gateway -- wget -qO- -T 5 http://<service>:<port>/health
   ```
   Healthy but `up == 0` points to scraping: a wrong port or a `/metrics` that
   hangs. Unhealthy usually means a dependency is down: Postgres (`5432`),
   Redis (`6379`), LocalStack (`4566`) or MeiliSearch (`7700`). Check those
   containers or pods next.

**Known, not a new incident:** `admin-service` crash-loops on boot on the
golden app (`services/admin-service/config/environments/production.rb`, the
planted bug in `AGENTS.md`). Do not fix it. Treat `ServiceDown{job="admin-service"}`
as expected unless the branch says otherwise.

## Mitigate

- Restart one stuck instance:
  `docker compose -f docker-compose.yml -f docker-compose.infra.yml restart <service>`, or
  `kubectl -n otterworks-<tenant> rollout restart deploy/<service>`.
- Bad deploy: `kubectl -n otterworks-<tenant> rollout undo deploy/<service>`, or
  redeploy the previous image the way the tenant was deployed
  (`docs/MULTI-TENANT-RUNBOOK.md`).

## How to tell it is fixed

- `up{job="<service>"}` is `1` on every instance for at least 2 minutes, and
  the alert has resolved in Alertmanager (`$AM/#/alerts`).
- The restart count stops climbing:
  `changes(process_start_time_seconds{job="<service>"}[15m])`. If it keeps
  climbing, `ServiceHighRestartRate` follows.
- A real request through the gateway succeeds, for example
  `curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/health`.

## Escalate when

- The service is still down 15 minutes after a restart or rollback, or it comes
  back and dies again.
- More than one service is down at the same time (a platform, node or
  datastore problem).
- The down service is `auth-service` or `api-gateway`: every user is locked
  out, so escalate right away.

**Where to run the commands**

| | Local Compose stack | Shared EKS cluster (`otterworks-dev`) |
|---|---|---|
| Prometheus | `http://localhost:9090` | `kubectl -n monitoring port-forward svc/prometheus-prometheus 19090:9090` |
| Grafana | `http://localhost:3001` (`admin` / `otterworks`) | `https://grafana.otterworks.app` |
| Alertmanager | `http://localhost:9093` | `kubectl -n monitoring port-forward svc/prometheus-alertmanager 19093:9093` |
| Jaeger | `http://localhost:16686` | `https://jaeger.otterworks.app` |
| Workloads | `docker compose -f docker-compose.yml -f docker-compose.infra.yml ps` | `kubectl -n otterworks-<tenant> get pods` (`otterworks-main` for t-main) |

Pods carry `app.kubernetes.io/name=<service>`. Compose containers are named
`otterworks-<service>`. In the commands below, `$PROM` is whichever Prometheus
URL applies (`export PROM=http://localhost:9090`).
