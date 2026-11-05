# Detection replay: cross-customer-access

- Started: 2026-11-05T13:24:43.125671+00:00
- Exit: 0
- Error: none
- seconds_to_fire is the first observed firing time, measured from attack start.

## Alerts

| Alert | Before | After | Seconds to fire | activeAt |
|---|---|---|---|---|
| SecurityCrossOwnerAccess | inactive | firing | 33.058 | ['2026-11-05T13:25:59.931387727Z'] |
| SecurityOwnerOverride | inactive | firing | 33.058 | ['2026-11-05T13:25:59.931387727Z'] |
| SecurityExportPathTraversal | inactive | firing | 33.058 | ['2026-11-05T13:25:59.931387727Z'] |

## Probe verdicts

- DAST-BOLA-DOCUMENTS: **secure** — the owner can read the document but the attacker got 403
- DAST-MASS-ASSIGNMENT-OWNER: **vulnerable** — attacker created document 5218af57-768c-4f69-87b0-b8d9b0629f4b owned by the victim (bfba0688-014f-4b39-b444-89753409442e) using only the attacker's own token
- DAST-PATH-TRAVERSAL-EXPORT: **vulnerable** — name='../../../../etc/passwd' returned a file from outside the export archive

## Before counters

```json
{
  "at": "2026-11-05T13:25:43.306353+00:00",
  "counters": {
    "otterworks_authz_events_total": [
      {
        "metric": {
          "__name__": "otterworks_authz_events_total",
          "event": "cross_owner_object",
          "instance": "document-service",
          "job": "document-service",
          "language": "python",
          "outcome": "denied",
          "service": "document-service",
          "tier": "backend"
        },
        "value": [
          1793885143.305,
          "4"
        ]
      },
      {
        "metric": {
          "__name__": "otterworks_authz_events_total",
          "event": "cross_owner_object",
          "instance": "document-service",
          "job": "document-service",
          "language": "python",
          "outcome": "allowed",
          "service": "document-service",
          "tier": "backend"
        },
        "value": [
          1793885143.305,
          "6"
        ]
      },
      {
        "metric": {
          "__name__": "otterworks_authz_events_total",
          "event": "owner_override",
          "instance": "document-service",
          "job": "document-service",
          "language": "python",
          "outcome": "observed",
          "service": "document-service",
          "tier": "backend"
        },
        "value": [
          1793885143.305,
          "1"
        ]
      },
      {
        "metric": {
          "__name__": "otterworks_authz_events_total",
          "event": "export_path_traversal",
          "instance": "document-service",
          "job": "document-service",
          "language": "python",
          "outcome": "observed",
          "service": "document-service",
          "tier": "backend"
        },
        "value": [
          1793885143.305,
          "1"
        ]
      }
    ]
  }
}
```

## After counters

```json
{
  "at": "2026-11-05T13:26:25.393961+00:00",
  "counters": {
    "otterworks_authz_events_total": [
      {
        "metric": {
          "__name__": "otterworks_authz_events_total",
          "event": "cross_owner_object",
          "instance": "document-service",
          "job": "document-service",
          "language": "python",
          "outcome": "denied",
          "service": "document-service",
          "tier": "backend"
        },
        "value": [
          1793885185.392,
          "5"
        ]
      },
      {
        "metric": {
          "__name__": "otterworks_authz_events_total",
          "event": "cross_owner_object",
          "instance": "document-service",
          "job": "document-service",
          "language": "python",
          "outcome": "allowed",
          "service": "document-service",
          "tier": "backend"
        },
        "value": [
          1793885185.392,
          "6"
        ]
      },
      {
        "metric": {
          "__name__": "otterworks_authz_events_total",
          "event": "owner_override",
          "instance": "document-service",
          "job": "document-service",
          "language": "python",
          "outcome": "observed",
          "service": "document-service",
          "tier": "backend"
        },
        "value": [
          1793885185.392,
          "2"
        ]
      },
      {
        "metric": {
          "__name__": "otterworks_authz_events_total",
          "event": "export_path_traversal",
          "instance": "document-service",
          "job": "document-service",
          "language": "python",
          "outcome": "observed",
          "service": "document-service",
          "tier": "backend"
        },
        "value": [
          1793885185.392,
          "2"
        ]
      }
    ]
  }
}
```

## Before alert states

```json
{
  "SecurityCrossOwnerAccess": {
    "state": "inactive",
    "instances": []
  },
  "SecurityOwnerOverride": {
    "state": "inactive",
    "instances": []
  },
  "SecurityExportPathTraversal": {
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
  "SecurityCrossOwnerAccess": {
    "state": "firing",
    "instances": [
      {
        "labels": {
          "alertname": "SecurityCrossOwnerAccess",
          "attack_class": "cross-customer-access",
          "page": "security",
          "severity": "critical"
        },
        "state": "firing",
        "activeAt": "2026-11-05T13:25:59.931387727Z",
        "value": "1.1428571428571428e+00"
      }
    ]
  },
  "SecurityOwnerOverride": {
    "state": "firing",
    "instances": [
      {
        "labels": {
          "alertname": "SecurityOwnerOverride",
          "attack_class": "cross-customer-access",
          "page": "security",
          "severity": "critical"
        },
        "state": "firing",
        "activeAt": "2026-11-05T13:25:59.931387727Z",
        "value": "1.1428571428571428e+00"
      }
    ]
  },
  "SecurityExportPathTraversal": {
    "state": "firing",
    "instances": [
      {
        "labels": {
          "alertname": "SecurityExportPathTraversal",
          "attack_class": "cross-customer-access",
          "page": "security",
          "severity": "critical"
        },
        "state": "firing",
        "activeAt": "2026-11-05T13:25:59.931387727Z",
        "value": "1.1428571428571428e+00"
      }
    ]
  }
}
```

## Captured security sink payloads

```json
[
  {
    "received_at": "2026-11-05T13:26:24Z",
    "receiver": "security",
    "headers": {
      "Host": "alert-sink:9095",
      "User-Agent": "Alertmanager/0.28.1",
      "Content-Length": "1757",
      "Content-Type": "application/json"
    },
    "payload": {
      "receiver": "security-oncall",
      "status": "firing",
      "alerts": [
        {
          "status": "firing",
          "labels": {
            "alertname": "SecurityOwnerOverride",
            "attack_class": "cross-customer-access",
            "cluster": "otterworks-dev",
            "environment": "development",
            "page": "security",
            "severity": "critical"
          },
          "annotations": {
            "description": "Document body names a different owner in the last two minutes. Observation is not proof of exploitation; correlate with the DAST report and request logs.",
            "finding_ids": "DAST-MASS-ASSIGNMENT-OWNER",
            "runbook_url": "https://github.com/Cognition-Partner-Workshops/otterworks/blob/main/security/detection/README.md#cross-customer-access",
            "summary": "Document body names a different owner"
          },
          "startsAt": "2026-11-05T13:26:14.931Z",
          "endsAt": "0001-01-01T00:00:00Z",
          "generatorURL": "http://6123f82cd608:9090/graph?g0.expr=sum%28increase%28otterworks_authz_events_total%7Bevent%3D%22owner_override%22%7D%5B2m%5D%29%29+%3E+0&g0.tab=1",
          "fingerprint": "b212e55eb3ce178d"
        }
      ],
      "groupLabels": {
        "alertname": "SecurityOwnerOverride"
      },
      "commonLabels": {
        "alertname": "SecurityOwnerOverride",
        "attack_class": "cross-customer-access",
        "cluster": "otterworks-dev",
        "environment": "development",
        "page": "security",
        "severity": "critical"
      },
      "commonAnnotations": {
        "description": "Document body names a different owner in the last two minutes. Observation is not proof of exploitation; correlate with the DAST report and request logs.",
        "finding_ids": "DAST-MASS-ASSIGNMENT-OWNER",
        "runbook_url": "https://github.com/Cognition-Partner-Workshops/otterworks/blob/main/security/detection/README.md#cross-customer-access",
        "summary": "Document body names a different owner"
      },
      "externalURL": "http://709abb884f29:9093",
      "version": "4",
      "groupKey": "{}/{page=\"security\"}:{alertname=\"SecurityOwnerOverride\"}",
      "truncatedAlerts": 0
    }
  },
  {
    "received_at": "2026-11-05T13:26:24Z",
    "receiver": "security",
    "headers": {
      "Host": "alert-sink:9095",
      "User-Agent": "Alertmanager/0.28.1",
      "Content-Length": "1796",
      "Content-Type": "application/json"
    },
    "payload": {
      "receiver": "security-oncall",
      "status": "firing",
      "alerts": [
        {
          "status": "firing",
          "labels": {
            "alertname": "SecurityExportPathTraversal",
            "attack_class": "cross-customer-access",
            "cluster": "otterworks-dev",
            "environment": "development",
            "page": "security",
            "severity": "critical"
          },
          "annotations": {
            "description": "Suspicious export archive path observed in the last two minutes. Observation is not proof of exploitation; correlate with the DAST report and request logs.",
            "finding_ids": "DAST-PATH-TRAVERSAL-EXPORT",
            "runbook_url": "https://github.com/Cognition-Partner-Workshops/otterworks/blob/main/security/detection/README.md#cross-customer-access",
            "summary": "Suspicious export archive path observed"
          },
          "startsAt": "2026-11-05T13:26:14.931Z",
          "endsAt": "0001-01-01T00:00:00Z",
          "generatorURL": "http://6123f82cd608:9090/graph?g0.expr=sum%28increase%28otterworks_authz_events_total%7Bevent%3D%22export_path_traversal%22%7D%5B2m%5D%29%29+%3E+0&g0.tab=1",
          "fingerprint": "6ee6288999a3335b"
        }
      ],
      "groupLabels": {
        "alertname": "SecurityExportPathTraversal"
      },
      "commonLabels": {
        "alertname": "SecurityExportPathTraversal",
        "attack_class": "cross-customer-access",
        "cluster": "otterworks-dev",
        "environment": "development",
        "page": "security",
        "severity": "critical"
      },
      "commonAnnotations": {
        "description": "Suspicious export archive path observed in the last two minutes. Observation is not proof of exploitation; correlate with the DAST report and request logs.",
        "finding_ids": "DAST-PATH-TRAVERSAL-EXPORT",
        "runbook_url": "https://github.com/Cognition-Partner-Workshops/otterworks/blob/main/security/detection/README.md#cross-customer-access",
        "summary": "Suspicious export archive path observed"
      },
      "externalURL": "http://709abb884f29:9093",
      "version": "4",
      "groupKey": "{}/{page=\"security\"}:{alertname=\"SecurityExportPathTraversal\"}",
      "truncatedAlerts": 0
    }
  },
  {
    "received_at": "2026-11-05T13:26:24Z",
    "receiver": "security",
    "headers": {
      "Host": "alert-sink:9095",
      "User-Agent": "Alertmanager/0.28.1",
      "Content-Length": "1755",
      "Content-Type": "application/json"
    },
    "payload": {
      "receiver": "security-oncall",
      "status": "firing",
      "alerts": [
        {
          "status": "firing",
          "labels": {
            "alertname": "SecurityCrossOwnerAccess",
            "attack_class": "cross-customer-access",
            "cluster": "otterworks-dev",
            "environment": "development",
            "page": "security",
            "severity": "critical"
          },
          "annotations": {
            "description": "Cross-owner document access observed in the last two minutes. Observation is not proof of exploitation; correlate with the DAST report and request logs.",
            "finding_ids": "DAST-BOLA-DOCUMENTS",
            "runbook_url": "https://github.com/Cognition-Partner-Workshops/otterworks/blob/main/security/detection/README.md#cross-customer-access",
            "summary": "Cross-owner document access observed"
          },
          "startsAt": "2026-11-05T13:26:14.931Z",
          "endsAt": "0001-01-01T00:00:00Z",
          "generatorURL": "http://6123f82cd608:9090/graph?g0.expr=sum%28increase%28otterworks_authz_events_total%7Bevent%3D%22cross_owner_object%22%7D%5B2m%5D%29%29+%3E+0&g0.tab=1",
          "fingerprint": "6328a5f49b5c85a1"
        }
      ],
      "groupLabels": {
        "alertname": "SecurityCrossOwnerAccess"
      },
      "commonLabels": {
        "alertname": "SecurityCrossOwnerAccess",
        "attack_class": "cross-customer-access",
        "cluster": "otterworks-dev",
        "environment": "development",
        "page": "security",
        "severity": "critical"
      },
      "commonAnnotations": {
        "description": "Cross-owner document access observed in the last two minutes. Observation is not proof of exploitation; correlate with the DAST report and request logs.",
        "finding_ids": "DAST-BOLA-DOCUMENTS",
        "runbook_url": "https://github.com/Cognition-Partner-Workshops/otterworks/blob/main/security/detection/README.md#cross-customer-access",
        "summary": "Cross-owner document access observed"
      },
      "externalURL": "http://709abb884f29:9093",
      "version": "4",
      "groupKey": "{}/{page=\"security\"}:{alertname=\"SecurityCrossOwnerAccess\"}",
      "truncatedAlerts": 0
    }
  }
]
```
