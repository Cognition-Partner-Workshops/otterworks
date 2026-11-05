# Detection replay: fin-privileged-endpoint

- Started: 2026-11-05T18:50:43.680867+00:00
- Exit: 0
- Error: none
- seconds_to_fire is the first observed firing time, measured from attack start.

## Alerts

| Alert | Before | After | Seconds to fire | activeAt |
|---|---|---|---|---|
| SecurityFineractPrivilegedEndpoint | inactive | firing | 27.16 | ['2026-11-05T18:51:55.539094344Z'] |

## Probe verdicts

- FIN-PRIVILEGED-ENDPOINT: **inconclusive** — Edge requests only; actor office and permissions are not evaluated; no Fineract is deployed. POST /datatables/deregister/detection-replay -> 404; POST /creditBureauIntegration/addCreditReport -> 404; POST /api/v1/datatables/deregister/detection-replay -> 404; POST /api/v1/creditBureauIntegration/addCreditReport -> 404; POST /fineract-provider/api/v1/datatables/deregister/detection-replay -> 404; POST /fineract-provider/api/v1/creditBureauIntegration/addCreditReport -> 404

## Before counters

```json
{
  "at": "2026-11-05T18:51:43.799847+00:00",
  "counters": {
    "api_gateway_security_events_total{event=\"fineract_privileged_endpoint\"}": [
      {
        "metric": {
          "__name__": "api_gateway_security_events_total",
          "event": "fineract_privileged_endpoint",
          "instance": "api-gateway",
          "job": "api-gateway",
          "language": "go",
          "reason": "credit_report_add",
          "service": "api-gateway",
          "tier": "gateway"
        },
        "value": [
          1793904703.798,
          "0"
        ]
      },
      {
        "metric": {
          "__name__": "api_gateway_security_events_total",
          "event": "fineract_privileged_endpoint",
          "instance": "api-gateway",
          "job": "api-gateway",
          "language": "go",
          "reason": "datatable_deregister",
          "service": "api-gateway",
          "tier": "gateway"
        },
        "value": [
          1793904703.798,
          "0"
        ]
      }
    ]
  }
}
```

## After counters

```json
{
  "at": "2026-11-05T18:52:22.996162+00:00",
  "counters": {
    "api_gateway_security_events_total{event=\"fineract_privileged_endpoint\"}": [
      {
        "metric": {
          "__name__": "api_gateway_security_events_total",
          "event": "fineract_privileged_endpoint",
          "instance": "api-gateway",
          "job": "api-gateway",
          "language": "go",
          "reason": "credit_report_add",
          "service": "api-gateway",
          "tier": "gateway"
        },
        "value": [
          1793904742.995,
          "3"
        ]
      },
      {
        "metric": {
          "__name__": "api_gateway_security_events_total",
          "event": "fineract_privileged_endpoint",
          "instance": "api-gateway",
          "job": "api-gateway",
          "language": "go",
          "reason": "datatable_deregister",
          "service": "api-gateway",
          "tier": "gateway"
        },
        "value": [
          1793904742.995,
          "3"
        ]
      }
    ]
  }
}
```

## Before alert states

```json
{
  "SecurityFineractPrivilegedEndpoint": {
    "state": "inactive",
    "instances": []
  }
}
```

## Before Alertmanager alerts

```json
[]
```

## After alert states

```json
{
  "SecurityFineractPrivilegedEndpoint": {
    "state": "firing",
    "instances": [
      {
        "labels": {
          "alertname": "SecurityFineractPrivilegedEndpoint",
          "attack_class": "fin-privileged-endpoint",
          "confirmation": "verified-path",
          "page": "security",
          "severity": "critical",
          "source": "fineract-edge"
        },
        "state": "firing",
        "activeAt": "2026-11-05T18:51:55.539094344Z",
        "value": "6.359428571428571e+00"
      }
    ]
  }
}
```

## Captured security sink payloads

```json
[
  {
    "received_at": "2026-11-05T18:52:20Z",
    "receiver": "security",
    "headers": {
      "Host": "alert-sink:9095",
      "User-Agent": "Alertmanager/0.28.1",
      "Content-Length": "1929",
      "Content-Type": "application/json"
    },
    "payload": {
      "receiver": "security-oncall",
      "status": "firing",
      "alerts": [
        {
          "status": "firing",
          "labels": {
            "alertname": "SecurityFineractPrivilegedEndpoint",
            "attack_class": "fin-privileged-endpoint",
            "cluster": "otterworks-dev",
            "confirmation": "verified-path",
            "environment": "development",
            "page": "security",
            "severity": "critical",
            "source": "fineract-edge"
          },
          "annotations": {
            "description": "Verified request path only: the actor's office and permissions are not evaluated. No Fineract is deployed here; responses remain unchanged.",
            "finding_ids": "FIN-PRIVILEGED-ENDPOINT",
            "runbook_url": "https://github.com/Cognition-Partner-Workshops/otterworks/blob/main/security/detection/README.md#fin-privileged-endpoint",
            "summary": "Fineract privileged endpoint request observed"
          },
          "startsAt": "2026-11-05T18:52:10.539Z",
          "endsAt": "0001-01-01T00:00:00Z",
          "generatorURL": "http://6123f82cd608:9090/graph?g0.expr=sum%28increase%28api_gateway_security_events_total%7Bevent%3D%22fineract_privileged_endpoint%22%7D%5B2m%5D%29%29+%3E+0&g0.tab=1",
          "fingerprint": "03d82a6c4ef61445"
        }
      ],
      "groupLabels": {
        "alertname": "SecurityFineractPrivilegedEndpoint"
      },
      "commonLabels": {
        "alertname": "SecurityFineractPrivilegedEndpoint",
        "attack_class": "fin-privileged-endpoint",
        "cluster": "otterworks-dev",
        "confirmation": "verified-path",
        "environment": "development",
        "page": "security",
        "severity": "critical",
        "source": "fineract-edge"
      },
      "commonAnnotations": {
        "description": "Verified request path only: the actor's office and permissions are not evaluated. No Fineract is deployed here; responses remain unchanged.",
        "finding_ids": "FIN-PRIVILEGED-ENDPOINT",
        "runbook_url": "https://github.com/Cognition-Partner-Workshops/otterworks/blob/main/security/detection/README.md#fin-privileged-endpoint",
        "summary": "Fineract privileged endpoint request observed"
      },
      "externalURL": "http://709abb884f29:9093",
      "version": "4",
      "groupKey": "{}/{page=\"security\"}:{alertname=\"SecurityFineractPrivilegedEndpoint\"}",
      "truncatedAlerts": 0
    }
  }
]
```
