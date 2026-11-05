# Detection replay: fin-makerchecker-repeat

- Started: 2026-11-05T18:47:04.040873+00:00
- Exit: 0
- Error: none
- seconds_to_fire is the first observed firing time, measured from attack start.

## Alerts

| Alert | Before | After | Seconds to fire | activeAt |
|---|---|---|---|---|
| SecurityFineractMakerCheckerRepeatApprove | inactive | firing | 36.29 | ['2026-11-05T18:48:25.175018976Z'] |

## Probe verdicts

- FIN-MAKERCHECKER-REPEAT: **inconclusive** — Edge requests only; actor office and permissions are not evaluated; no Fineract is deployed. POST /makercheckers/559761867?command=approve -> 404; POST /makercheckers/559761867?command=approve -> 404; POST /api/v1/makercheckers/1702618635?command=approve -> 404; POST /api/v1/makercheckers/1702618635?command=approve -> 404; POST /fineract-provider/api/v1/makercheckers/1585788167?command=approve -> 404; POST /fineract-provider/api/v1/makercheckers/1585788167?command=approve -> 404

## Before counters

```json
{
  "at": "2026-11-05T18:48:04.173545+00:00",
  "counters": {
    "api_gateway_security_events_total{event=\"fineract_makerchecker_repeat_approve\"}": [
      {
        "metric": {
          "__name__": "api_gateway_security_events_total",
          "event": "fineract_makerchecker_repeat_approve",
          "instance": "api-gateway",
          "job": "api-gateway",
          "language": "go",
          "reason": "within_window",
          "service": "api-gateway",
          "tier": "gateway"
        },
        "value": [
          1793904484.172,
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
  "at": "2026-11-05T18:48:52.490699+00:00",
  "counters": {
    "api_gateway_security_events_total{event=\"fineract_makerchecker_repeat_approve\"}": [
      {
        "metric": {
          "__name__": "api_gateway_security_events_total",
          "event": "fineract_makerchecker_repeat_approve",
          "instance": "api-gateway",
          "job": "api-gateway",
          "language": "go",
          "reason": "within_window",
          "service": "api-gateway",
          "tier": "gateway"
        },
        "value": [
          1793904532.489,
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
  "SecurityFineractMakerCheckerRepeatApprove": {
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
  "SecurityFineractMakerCheckerRepeatApprove": {
    "state": "firing",
    "instances": [
      {
        "labels": {
          "alertname": "SecurityFineractMakerCheckerRepeatApprove",
          "attack_class": "fin-makerchecker-repeat",
          "confirmation": "verified-path",
          "page": "security",
          "severity": "critical",
          "source": "fineract-edge"
        },
        "state": "firing",
        "activeAt": "2026-11-05T18:48:25.175018976Z",
        "value": "3.1975333333333333e+00"
      }
    ]
  }
}
```

## Captured security sink payloads

```json
[
  {
    "received_at": "2026-11-05T18:48:50Z",
    "receiver": "security",
    "headers": {
      "Host": "alert-sink:9095",
      "User-Agent": "Alertmanager/0.28.1",
      "Content-Length": "1969",
      "Content-Type": "application/json"
    },
    "payload": {
      "receiver": "security-oncall",
      "status": "firing",
      "alerts": [
        {
          "status": "firing",
          "labels": {
            "alertname": "SecurityFineractMakerCheckerRepeatApprove",
            "attack_class": "fin-makerchecker-repeat",
            "cluster": "otterworks-dev",
            "confirmation": "verified-path",
            "environment": "development",
            "page": "security",
            "severity": "critical",
            "source": "fineract-edge"
          },
          "annotations": {
            "description": "Verified request path only: the actor's office and permissions are not evaluated. No Fineract is deployed here; responses remain unchanged.",
            "finding_ids": "FIN-MAKERCHECKER-REPEAT",
            "runbook_url": "https://github.com/Cognition-Partner-Workshops/otterworks/blob/main/security/detection/README.md#fin-makerchecker-repeat",
            "summary": "Repeated maker-checker approve request observed"
          },
          "startsAt": "2026-11-05T18:48:40.175Z",
          "endsAt": "0001-01-01T00:00:00Z",
          "generatorURL": "http://6123f82cd608:9090/graph?g0.expr=sum%28increase%28api_gateway_security_events_total%7Bevent%3D%22fineract_makerchecker_repeat_approve%22%7D%5B2m%5D%29%29+%3E+0&g0.tab=1",
          "fingerprint": "1472985340f19f20"
        }
      ],
      "groupLabels": {
        "alertname": "SecurityFineractMakerCheckerRepeatApprove"
      },
      "commonLabels": {
        "alertname": "SecurityFineractMakerCheckerRepeatApprove",
        "attack_class": "fin-makerchecker-repeat",
        "cluster": "otterworks-dev",
        "confirmation": "verified-path",
        "environment": "development",
        "page": "security",
        "severity": "critical",
        "source": "fineract-edge"
      },
      "commonAnnotations": {
        "description": "Verified request path only: the actor's office and permissions are not evaluated. No Fineract is deployed here; responses remain unchanged.",
        "finding_ids": "FIN-MAKERCHECKER-REPEAT",
        "runbook_url": "https://github.com/Cognition-Partner-Workshops/otterworks/blob/main/security/detection/README.md#fin-makerchecker-repeat",
        "summary": "Repeated maker-checker approve request observed"
      },
      "externalURL": "http://709abb884f29:9093",
      "version": "4",
      "groupKey": "{}/{page=\"security\"}:{alertname=\"SecurityFineractMakerCheckerRepeatApprove\"}",
      "truncatedAlerts": 0
    }
  }
]
```
