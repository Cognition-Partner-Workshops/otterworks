# Edge latency by client in CloudWatch

The api-gateway writes one JSON access log line per request. Each line carries
`method`, `route`, `status`, `duration_ms` and `client`, where `client` comes
from the User-Agent:

| client    | User-Agent contains                          |
|-----------|----------------------------------------------|
| `ios`     | `OtterWorksApp/ios` (Capacitor iOS shell)     |
| `android` | `OtterWorksApp/android` (Capacitor Android)   |
| `web`     | any other `Mozilla/...` browser string        |
| `other`   | curl, health checks, SDKs, empty             |

`route` is the path with ids collapsed, so `/api/v1/files/<uuid>` logs as
`/api/v1/files/:id`. The file list is `GET /api/v1/files`.

## Log groups

Fluent Bit (`scripts/install-log-shipping.sh`, values in
`infrastructure/helm/aws-for-fluent-bit/`) ships two containers for every
`otterworks-*` namespace:

```
/otterworks/eks/otterworks-dev/<namespace>/api-gateway
/otterworks/eks/otterworks-dev/<namespace>/ingress-nginx
```

with 7-day retention on both. The ingress-nginx group holds the shared controller's
lines for requests routed to that namespace, with the same `route`,
`duration_ms` and `client` fields added by the Fluent Bit Lua filter. Use the
api-gateway group to see time spent inside the gateway, and the ingress-nginx
group to see what the caller waited end to end.

## Logs Insights queries

Pick the tenant's api-gateway log group, for example
`/otterworks/eks/otterworks-dev/otterworks-mob-20261006/api-gateway`.

p95 duration by client for the file list:

```
filter route = "/api/v1/files" and method = "GET"
| stats pct(duration_ms, 95) as p95_ms, count(*) as requests by client
| sort client
```

p95 duration by client, split by route:

```
filter ispresent(route) and ispresent(client)
| stats pct(duration_ms, 95) as p95_ms, count(*) as requests by route, client
| sort route, client
```

From the CLI:

```bash
aws logs start-query --region us-east-1 \
  --log-group-name /otterworks/eks/otterworks-dev/otterworks-<tenant>/api-gateway \
  --start-time $(( $(date +%s) - 3600 )) --end-time $(date +%s) \
  --query-string 'filter route = "/api/v1/files" and method = "GET" | stats pct(duration_ms, 95) as p95_ms, count(*) as requests by client | sort client'
aws logs get-query-results --region us-east-1 --query-id <id>
```

## Native-only latency on the file list

api-gateway used to sleep in front of `GET /api/v1/files` whenever the
User-Agent carried `OtterWorksApp` and the tenant Redis held
`chaos:api-gateway:mobile_latency_ms`, which made the iOS and Android Files
screen wait about 3 s while browsers were unaffected. That hook has been
removed; the first query above should show `ios`, `android` and `web` within
the same range on `/api/v1/files`.
