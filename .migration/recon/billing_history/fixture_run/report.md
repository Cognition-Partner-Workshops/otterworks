# Recon report: unit `billing_history`

- **parity PASS, merge blocked (evidence, rerun_policy, structural)**
- Verdict: PASS (all tiers)
- Blockers: structural: structural_gap, warnings; evidence: routine_parity_missing, mode; rerun_policy: rerun_missing
- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Rerun posture: `first_run_baseline`
- Merge authority: `harness` (human_override needs a merge_overrides entry in the committed wave manifest naming the unit)
- Mapping version: `map-v1`
- Tolerance version: `tol-20261027-v1`
- Seed: `0`
- Tier 3 depth: `sampled`
- Generated: 2026-10-28T01:12:29.506585+00:00

## Routine parity: routine_parity_missing (the unit has writing routines and no parity list; run `dbx-recon routine-parity` and pass `--routine-parity`)

- `snapshot.customer_master` no row
- `snapshot.customer_master_hist` no row
- `snapshot.entity_attr_value` no row
- `snapshot.invoice_header` no row
- `snapshot.invoice_line` no row
- Cost: `{"source_statements": 506, "source_rows_fetched": 304342, "target_statements": 347, "target_rows_fetched": 152107, "elapsed_s": 190.508}`
- **WARNING: UNVERIFIED structural_parity: structure unavailable: customer_master: customer_master: information_schema.table_privileges read failed (ServerOperationError)**
- **WARNING: UNVERIFIED structural_parity: structure unavailable: customer_master_hist: customer_master_hist: information_schema.table_privileges read failed (ServerOperationError)**
- **WARNING: UNVERIFIED structural_parity: structure unavailable: entity_attr_value: entity_attr_value: information_schema.table_privileges read failed (ServerOperationError)**
- **WARNING: UNVERIFIED structural_parity: structure unavailable: invoice_header: invoice_header: information_schema.table_privileges read failed (ServerOperationError)**
- **WARNING: UNVERIFIED structural_parity: structure unavailable: invoice_line: invoice_line: information_schema.table_privileges read failed (ServerOperationError)**

| Tier | Name | Checks | Result |
|---|---|---|---|
| 0 | structural_parity | 0 | PASS |
| 1 | counts_through_mapping | 5 | PASS |
| 2 | per_field_aggregates | 0 | PASS |
| 3 | keyed_diffs | 152107 | PASS |

## Tier 0 coverage
```json
{
  "dictionary_unavailable": [
    "customer_master: customer_master: information_schema.table_privileges read failed (ServerOperationError)",
    "customer_master_hist: customer_master_hist: information_schema.table_privileges read failed (ServerOperationError)",
    "entity_attr_value: entity_attr_value: information_schema.table_privileges read failed (ServerOperationError)",
    "invoice_header: invoice_header: information_schema.table_privileges read failed (ServerOperationError)",
    "invoice_line: invoice_line: information_schema.table_privileges read failed (ServerOperationError)"
  ],
  "structural_checks": {
    "constraints": "unsupported",
    "triggers": "unsupported",
    "indexes": "unsupported",
    "sequences_identity": "unsupported",
    "grants": "unsupported"
  },
  "structural_diff": {},
  "dictionary": {
    "source": "live",
    "target": "live"
  },
  "hole_kinds": [
    "read"
  ]
}
```

## Tier 1 coverage
```json
{
  "source_counts": {
    "ow_billing.customer_master": 25001,
    "ow_billing.customer_master_hist": 0,
    "ow_billing.entity_attr_value": 8337,
    "ow_billing.invoice_header": 18750,
    "ow_billing.invoice_line": 150000
  }
}
```

## Tier 3 coverage
```json
{
  "customer_master": {
    "mode": "stratified_sample",
    "sampling": "stratified",
    "strata": 32,
    "population": 25001,
    "sampled": 25001,
    "coverage": 1.0,
    "null_key_rows": {
      "source": 0,
      "target": 0
    },
    "duplicate_source_key_count": 0
  },
  "customer_master_hist": {
    "mode": "stratified_sample",
    "sampling": "stratified",
    "strata": 0,
    "population": 0,
    "sampled": 0,
    "coverage": 1.0,
    "null_key_rows": {
      "source": 0,
      "target": 0
    },
    "duplicate_source_key_count": 0
  },
  "entity_attr_value": {
    "mode": "stratified_sample",
    "sampling": "stratified",
    "strata": 32,
    "population": 8337,
    "sampled": 8337,
    "coverage": 1.0,
    "null_key_rows": {
      "source": 0,
      "target": 0
    },
    "duplicate_source_key_count": 0
  },
  "invoice_header": {
    "mode": "stratified_sample",
    "sampling": "stratified",
    "strata": 32,
    "population": 18750,
    "sampled": 18750,
    "coverage": 1.0,
    "null_key_rows": {
      "source": 0,
      "target": 0
    },
    "duplicate_source_key_count": 0
  },
  "invoice_line": {
    "mode": "stratified_sample",
    "sampling": "stratified",
    "strata": 32,
    "population": 150000,
    "sampled": 100019,
    "coverage": 0.666793,
    "null_key_rows": {
      "source": 0,
      "target": 0
    },
    "duplicate_source_key_count": 0
  }
}
```
