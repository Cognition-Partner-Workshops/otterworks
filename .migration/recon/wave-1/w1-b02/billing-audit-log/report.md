# Recon report: unit `billing-audit-log`

- **Verdict: FAIL** (values redacted)
- Mode: `live`
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `map-v3` (sha256 `c158f8bb469d`)
- Tolerance version: `tol-1` (sha256 `a23d517a8e6d`)
- Collections: `billingAuditLog`
- Seed: `0`
- Generated: 2026-10-08T13:34:20.242758+00:00
- 3 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 2 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 1 | PASS |
| 2 | per_field_aggregates | 1 | FAIL (2 findings) |
| 3 | keyed_diffs | 37 | FAIL (37 findings) |

## Tier 1 coverage
```json
{
  "source_counts": {
    "billingAuditLog": 37
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "billingAuditLog.loggedAt",
    "billingAuditLog.module",
    "billingAuditLog.message"
  ],
  "string_aggregates_deferred_to_tier3": [
    {
      "field": "billingAuditLog.module",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "billingAuditLog.message",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    }
  ],
  "fields_fully_deferred": 2
}
```

## Tier 2 findings (2)
- `billingAuditLog` aggregate_min: field LOGGED_AT->loggedAt | source=datetime:330647912f41 target=datetime:8a0170ff10a6 | rules=['datetime_utc_truncate_ms']
- `billingAuditLog` aggregate_max: field LOGGED_AT->loggedAt | source=datetime:330647912f41 target=datetime:8a0170ff10a6 | rules=['datetime_utc_truncate_ms']

## Tier 3 coverage
```json
{
  "billingAuditLog": {
    "mode": "full_diff",
    "population": 37,
    "duplicate_source_key_count": 0
  }
}
```

## Tier 3 findings (37)
- `billingAuditLog` field_diff: field LOGGED_AT->loggedAt key=tuple:28cb03b06c28 | source=datetime:330647912f41 target=datetime:8a0170ff10a6 | rules=[]
- `billingAuditLog` field_diff: field LOGGED_AT->loggedAt key=tuple:0555debc8a65 | source=datetime:330647912f41 target=datetime:8a0170ff10a6 | rules=[]
- `billingAuditLog` field_diff: field LOGGED_AT->loggedAt key=tuple:4079e4af87d7 | source=datetime:330647912f41 target=datetime:8a0170ff10a6 | rules=[]
- `billingAuditLog` field_diff: field LOGGED_AT->loggedAt key=tuple:3912a1d67a34 | source=datetime:330647912f41 target=datetime:8a0170ff10a6 | rules=[]
- `billingAuditLog` field_diff: field LOGGED_AT->loggedAt key=tuple:666aa17826ad | source=datetime:330647912f41 target=datetime:8a0170ff10a6 | rules=[]
- `billingAuditLog` field_diff: field LOGGED_AT->loggedAt key=tuple:3af5d6e7f947 | source=datetime:330647912f41 target=datetime:8a0170ff10a6 | rules=[]
- `billingAuditLog` field_diff: field LOGGED_AT->loggedAt key=tuple:24a6ade6d35f | source=datetime:330647912f41 target=datetime:8a0170ff10a6 | rules=[]
- `billingAuditLog` field_diff: field LOGGED_AT->loggedAt key=tuple:8c98d396d4e2 | source=datetime:330647912f41 target=datetime:8a0170ff10a6 | rules=[]
- `billingAuditLog` field_diff: field LOGGED_AT->loggedAt key=tuple:6fd93f706bb5 | source=datetime:330647912f41 target=datetime:8a0170ff10a6 | rules=[]
- `billingAuditLog` field_diff: field LOGGED_AT->loggedAt key=tuple:3623a2e9858c | source=datetime:330647912f41 target=datetime:8a0170ff10a6 | rules=[]
- `billingAuditLog` field_diff: field LOGGED_AT->loggedAt key=tuple:d66a370d279e | source=datetime:330647912f41 target=datetime:8a0170ff10a6 | rules=[]
- `billingAuditLog` field_diff: field LOGGED_AT->loggedAt key=tuple:dfece6a4d633 | source=datetime:330647912f41 target=datetime:8a0170ff10a6 | rules=[]
- `billingAuditLog` field_diff: field LOGGED_AT->loggedAt key=tuple:f4998cc8d9fd | source=datetime:330647912f41 target=datetime:8a0170ff10a6 | rules=[]
- `billingAuditLog` field_diff: field LOGGED_AT->loggedAt key=tuple:187d5a0656b5 | source=datetime:330647912f41 target=datetime:8a0170ff10a6 | rules=[]
- `billingAuditLog` field_diff: field LOGGED_AT->loggedAt key=tuple:4fdda04c7f66 | source=datetime:330647912f41 target=datetime:8a0170ff10a6 | rules=[]
- `billingAuditLog` field_diff: field LOGGED_AT->loggedAt key=tuple:0a480dc88dda | source=datetime:330647912f41 target=datetime:8a0170ff10a6 | rules=[]
- `billingAuditLog` field_diff: field LOGGED_AT->loggedAt key=tuple:78232db12513 | source=datetime:330647912f41 target=datetime:8a0170ff10a6 | rules=[]
- `billingAuditLog` field_diff: field LOGGED_AT->loggedAt key=tuple:25cfb52fcfe2 | source=datetime:330647912f41 target=datetime:8a0170ff10a6 | rules=[]
- `billingAuditLog` field_diff: field LOGGED_AT->loggedAt key=tuple:d9220edbfa6b | source=datetime:330647912f41 target=datetime:8a0170ff10a6 | rules=[]
- `billingAuditLog` field_diff: field LOGGED_AT->loggedAt key=tuple:821902cf7e59 | source=datetime:330647912f41 target=datetime:8a0170ff10a6 | rules=[]
- `billingAuditLog` field_diff: field LOGGED_AT->loggedAt key=tuple:dafc7efeb735 | source=datetime:330647912f41 target=datetime:8a0170ff10a6 | rules=[]
- `billingAuditLog` field_diff: field LOGGED_AT->loggedAt key=tuple:0e4fc813171d | source=datetime:330647912f41 target=datetime:8a0170ff10a6 | rules=[]
- `billingAuditLog` field_diff: field LOGGED_AT->loggedAt key=tuple:5503efdc6ad9 | source=datetime:330647912f41 target=datetime:8a0170ff10a6 | rules=[]
- `billingAuditLog` field_diff: field LOGGED_AT->loggedAt key=tuple:46ff29167351 | source=datetime:330647912f41 target=datetime:8a0170ff10a6 | rules=[]
- `billingAuditLog` field_diff: field LOGGED_AT->loggedAt key=tuple:67884d458137 | source=datetime:330647912f41 target=datetime:8a0170ff10a6 | rules=[]
- `billingAuditLog` field_diff: field LOGGED_AT->loggedAt key=tuple:29a680646cef | source=datetime:330647912f41 target=datetime:8a0170ff10a6 | rules=[]
- `billingAuditLog` field_diff: field LOGGED_AT->loggedAt key=tuple:ce7ccce47fb2 | source=datetime:330647912f41 target=datetime:8a0170ff10a6 | rules=[]
- `billingAuditLog` field_diff: field LOGGED_AT->loggedAt key=tuple:9f256d9b7934 | source=datetime:330647912f41 target=datetime:8a0170ff10a6 | rules=[]
- `billingAuditLog` field_diff: field LOGGED_AT->loggedAt key=tuple:7c077263a4b1 | source=datetime:330647912f41 target=datetime:8a0170ff10a6 | rules=[]
- `billingAuditLog` field_diff: field LOGGED_AT->loggedAt key=tuple:0d99aae3df50 | source=datetime:330647912f41 target=datetime:8a0170ff10a6 | rules=[]
- `billingAuditLog` field_diff: field LOGGED_AT->loggedAt key=tuple:f56a3e9962be | source=datetime:330647912f41 target=datetime:8a0170ff10a6 | rules=[]
- `billingAuditLog` field_diff: field LOGGED_AT->loggedAt key=tuple:ab344921928c | source=datetime:330647912f41 target=datetime:8a0170ff10a6 | rules=[]
- `billingAuditLog` field_diff: field LOGGED_AT->loggedAt key=tuple:bfa1862dfc3d | source=datetime:330647912f41 target=datetime:8a0170ff10a6 | rules=[]
- `billingAuditLog` field_diff: field LOGGED_AT->loggedAt key=tuple:a97f6d93c2ea | source=datetime:330647912f41 target=datetime:8a0170ff10a6 | rules=[]
- `billingAuditLog` field_diff: field LOGGED_AT->loggedAt key=tuple:d4109b4f7194 | source=datetime:330647912f41 target=datetime:8a0170ff10a6 | rules=[]
- `billingAuditLog` field_diff: field LOGGED_AT->loggedAt key=tuple:40f5a64b1398 | source=datetime:330647912f41 target=datetime:8a0170ff10a6 | rules=[]
- `billingAuditLog` field_diff: field LOGGED_AT->loggedAt key=tuple:b07cad823739 | source=datetime:330647912f41 target=datetime:8a0170ff10a6 | rules=[]
