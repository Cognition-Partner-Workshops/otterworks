# Detection replay: fin-makerchecker-disabled

- Started: 2026-11-05T18:48:53.887436+00:00
- Exit: 0
- Error: none
- seconds_to_fire is the first observed firing time, measured from attack start.

## Alerts

| Alert | Before | After | Seconds to fire | activeAt |
|---|---|---|---|---|
| SecurityFineractMakerCheckerDisabled | inactive | firing | 36.21 | ['2026-11-05T18:50:14.809867953Z'] |

## Probe verdicts

- FIN-MAKERCHECKER-DISABLED: **inconclusive** — Edge requests only; actor office and permissions are not evaluated; no Fineract is deployed. PUT /configurations/name/maker-checker -> 404; POST /configurations/1?command=disable -> 404; POST /configurations/name/maker-checker?command=disable -> 404; PUT /api/v1/configurations/name/maker-checker -> 404; POST /api/v1/configurations/1?command=disable -> 404; POST /api/v1/configurations/name/maker-checker?command=disable -> 404; PUT /fineract-provider/api/v1/configurations/name/maker-checker -> 404; POST /fineract-provider/api/v1/configurations/1?command=disable -> 404; POST /fineract-provider/api/v1/configurations/name/maker-checker?command=disable -> 404

## Before counters

```json
{
  "at": "2026-11-05T18:49:54.006196+00:00",
  "counters": {
    "api_gateway_security_events_total{event=\"fineract_maker_checker_disabled\"}": [
      {
        "metric": {
          "__name__": "api_gateway_security_events_total",
          "event": "fineract_maker_checker_disabled",
          "instance": "api-gateway",
          "job": "api-gateway",
          "language": "go",
          "reason": "command_disable",
          "service": "api-gateway",
          "tier": "gateway"
        },
        "value": [
          1793904594.005,
          "0"
        ]
      },
      {
        "metric": {
          "__name__": "api_gateway_security_events_total",
          "event": "fineract_maker_checker_disabled",
          "instance": "api-gateway",
          "job": "api-gateway",
          "language": "go",
          "reason": "config_put",
          "service": "api-gateway",
          "tier": "gateway"
        },
        "value": [
          1793904594.005,
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
  "at": "2026-11-05T18:50:42.241029+00:00",
  "counters": {
    "api_gateway_security_events_total{event=\"fineract_maker_checker_disabled\"}": [
      {
        "metric": {
          "__name__": "api_gateway_security_events_total",
          "event": "fineract_maker_checker_disabled",
          "instance": "api-gateway",
          "job": "api-gateway",
          "language": "go",
          "reason": "command_disable",
          "service": "api-gateway",
          "tier": "gateway"
        },
        "value": [
          1793904642.24,
          "6"
        ]
      },
      {
        "metric": {
          "__name__": "api_gateway_security_events_total",
          "event": "fineract_maker_checker_disabled",
          "instance": "api-gateway",
          "job": "api-gateway",
          "language": "go",
          "reason": "config_put",
          "service": "api-gateway",
          "tier": "gateway"
        },
        "value": [
          1793904642.24,
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
  "SecurityFineractMakerCheckerDisabled": {
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
  "SecurityFineractMakerCheckerDisabled": {
    "state": "firing",
    "instances": [
      {
        "labels": {
          "alertname": "SecurityFineractMakerCheckerDisabled",
          "attack_class": "fin-makerchecker-disabled",
          "confirmation": "verified-path",
          "page": "security",
          "severity": "critical",
          "source": "fineract-edge"
        },
        "state": "firing",
        "activeAt": "2026-11-05T18:50:14.809867953Z",
        "value": "9.905142857142856e+00"
      }
    ]
  }
}
```

## Captured security sink payloads

```json
[
  {
    "received_at": "2026-11-05T18:50:39Z",
    "receiver": "security",
    "headers": {
      "Host": "alert-sink:9095",
      "User-Agent": "Alertmanager/0.28.1",
      "Content-Length": "1942",
      "Content-Type": "application/json"
    },
    "payload": {
      "receiver": "security-oncall",
      "status": "firing",
      "alerts": [
        {
          "status": "firing",
          "labels": {
            "alertname": "SecurityFineractMakerCheckerDisabled",
            "attack_class": "fin-makerchecker-disabled",
            "cluster": "otterworks-dev",
            "confirmation": "verified-path",
            "environment": "development",
            "page": "security",
            "severity": "critical",
            "source": "fineract-edge"
          },
          "annotations": {
            "description": "Verified request path only: the actor's office and permissions are not evaluated. No Fineract is deployed here; responses remain unchanged.",
            "finding_ids": "FIN-MAKERCHECKER-DISABLED",
            "runbook_url": "https://github.com/Cognition-Partner-Workshops/otterworks/blob/main/security/detection/README.md#fin-makerchecker-disabled",
            "summary": "Maker-checker disabling request observed"
          },
          "startsAt": "2026-11-05T18:50:29.809Z",
          "endsAt": "0001-01-01T00:00:00Z",
          "generatorURL": "http://6123f82cd608:9090/graph?g0.expr=sum%28increase%28api_gateway_security_events_total%7Bevent%3D%22fineract_maker_checker_disabled%22%7D%5B2m%5D%29%29+%3E+0&g0.tab=1",
          "fingerprint": "ad17e858d88d07f7"
        }
      ],
      "groupLabels": {
        "alertname": "SecurityFineractMakerCheckerDisabled"
      },
      "commonLabels": {
        "alertname": "SecurityFineractMakerCheckerDisabled",
        "attack_class": "fin-makerchecker-disabled",
        "cluster": "otterworks-dev",
        "confirmation": "verified-path",
        "environment": "development",
        "page": "security",
        "severity": "critical",
        "source": "fineract-edge"
      },
      "commonAnnotations": {
        "description": "Verified request path only: the actor's office and permissions are not evaluated. No Fineract is deployed here; responses remain unchanged.",
        "finding_ids": "FIN-MAKERCHECKER-DISABLED",
        "runbook_url": "https://github.com/Cognition-Partner-Workshops/otterworks/blob/main/security/detection/README.md#fin-makerchecker-disabled",
        "summary": "Maker-checker disabling request observed"
      },
      "externalURL": "http://709abb884f29:9093",
      "version": "4",
      "groupKey": "{}/{page=\"security\"}:{alertname=\"SecurityFineractMakerCheckerDisabled\"}",
      "truncatedAlerts": 0
    }
  }
]
```
