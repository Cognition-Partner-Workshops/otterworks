# Recon report: unit `slice-0`

- **PARITY NOT_RUN (mode snapshot)**
- Mode: `snapshot` (PASS scoped to the snapshot watermark)
- Rerun posture: `required`
- Mapping version: `unt19-20261030-v1`
- Tolerance version: `tol-20261027-v1`
- Seed: `0`
- Tier 3 depth: `full`
- Generated: 2026-11-03T14:04:28.010273+00:00
- Snapshot provenance: `{"source": "oracle", "snapshot_at": "2026-10-31T22:31:25+00:00", "export_manifest": "https://github.com/Cognition-Partner-Workshops/otterworks/pull/2362 (.migration/recon/slice-0/out/export_manifest.json, commit 415b07336)", "row_counts": {"CODES": 32, "PLANS": 3, "TENANTS": 70, "BILLING_AUDIT_LOG": 0}}`
- Cost: `{"source_statements": 40, "source_rows_fetched": 105, "target_statements": 43, "target_rows_fetched": 105, "elapsed_s": 36.743}`

## Findings

- [structural] `codes` primary_key_mismatch: source () -> expected (), target ('code_type', 'code_val')
- [structural] `codes` not_null_extra: target code_desc is NOT NULL but its source column is nullable: legacy-valid NULLs would be rejected
- [structural] `plans` primary_key_mismatch: source () -> expected (), target ('id',)
- [structural] `plans` unique_extra: target unique ('code',) has no source counterpart: legacy-valid duplicates would be rejected
- [structural] `plans` not_null_extra: target active_yn is NOT NULL but its source column is nullable: legacy-valid NULLs would be rejected
- [structural] `plans` not_null_extra: target code is NOT NULL but its source column is nullable: legacy-valid NULLs would be rejected
- [structural] `plans` not_null_extra: target included_units is NOT NULL but its source column is nullable: legacy-valid NULLs would be rejected
- [structural] `plans` not_null_extra: target monthly_fee is NOT NULL but its source column is nullable: legacy-valid NULLs would be rejected
- [structural] `plans` not_null_extra: target overage_rate is NOT NULL but its source column is nullable: legacy-valid NULLs would be rejected
- [structural] `plans` not_null_extra: target tier_cd is NOT NULL but its source column is nullable: legacy-valid NULLs would be rejected
- [structural] `tenants` primary_key_mismatch: source () -> expected (), target ('id',)
- [structural] `tenants` unique_extra: target unique ('name',) has no source counterpart: legacy-valid duplicates would be rejected
- [structural] `tenants` not_null_extra: target name is NOT NULL but its source column is nullable: legacy-valid NULLs would be rejected
- [structural] `tenants` not_null_extra: target status_cd is NOT NULL but its source column is nullable: legacy-valid NULLs would be rejected
- [structural] `tenants` not_null_extra: target tax_exempt_yn is NOT NULL but its source column is nullable: legacy-valid NULLs would be rejected
- [structural] `billing_audit_log` not_null_extra: target logged_at is NOT NULL but its source column is nullable: legacy-valid NULLs would be rejected
- [structural] `billing_audit_log` identity_extra: target log_id is identity but source log_id is not: target-generated keys diverge from the source's
- [evidence] `OW_BILLING.PKG_OW_UTIL.F_CODE_DESC` routine_parity_missing: writing routine has no routine_parity row
- [evidence] `OW_BILLING.PKG_OW_UTIL.F_DT2STR` routine_parity_missing: writing routine has no routine_parity row
- [evidence] `OW_BILLING.PKG_OW_UTIL.F_MD5_UUID` routine_parity_missing: writing routine has no routine_parity row
- [evidence] `OW_BILLING.PKG_OW_UTIL.F_STR2DT` routine_parity_missing: writing routine has no routine_parity row
- [evidence] `OW_BILLING.PKG_OW_UTIL.LOG_MSG` routine_parity_missing: writing routine has no routine_parity row
- [evidence] `OW_BILLING.TRG_BILLING_AUDIT_LOG_ID` routine_parity_missing: writing routine has no routine_parity row
- [evidence] `ow_billing.pkg_ow_util.log_msg` routine_parity_missing: writing routine has no routine_parity row
- [evidence] `billing_audit_log` by_design_unverified: object graded by_design_unverified: values not graded
- [rerun_policy] `slice-0` rerun_missing: no rerun proof for this slice

| Tier | Name | Checks | Result |
|---|---|---|---|
| 0 | structural_parity | 4 | FAIL (17 findings) |
| 1 | counts_through_mapping | 4 | PASS |
| 2 | per_field_aggregates | 14 | PASS |
| 3 | keyed_diffs | 105 | PASS |

## Tier 0 coverage
```json
{
  "codes": {
    "source": {
      "table_type": null,
      "primary_key": [],
      "primary_key_informational": [],
      "unique": [],
      "unique_nulls_equal": [],
      "foreign_keys": [],
      "foreign_keys_informational": [],
      "not_null": [],
      "indexes": [],
      "check_count": 0,
      "checks": [],
      "identity_columns": [],
      "partial": [],
      "expression_unique": [],
      "expression_indexes": [],
      "triggers": {},
      "grants": {},
      "unsupported": [
        "indexes"
      ],
      "privilege_denied": []
    },
    "target": {
      "table_type": null,
      "primary_key": [
        "code_type",
        "code_val"
      ],
      "primary_key_informational": [],
      "unique": [],
      "unique_nulls_equal": [],
      "foreign_keys": [],
      "foreign_keys_informational": [],
      "not_null": [
        "code_desc",
        "code_type",
        "code_val"
      ],
      "indexes": [],
      "check_count": 0,
      "checks": [],
      "identity_columns": [],
      "partial": [],
      "expression_unique": [],
      "expression_indexes": [],
      "triggers": {},
      "grants": {},
      "unsupported": [],
      "privilege_denied": []
    },
    "identity": null
  },
  "plans": {
    "source": {
      "table_type": null,
      "primary_key": [],
      "primary_key_informational": [],
      "unique": [],
      "unique_nulls_equal": [],
      "foreign_keys": [],
      "foreign_keys_informational": [],
      "not_null": [],
      "indexes": [],
      "check_count": 0,
      "checks": [],
      "identity_columns": [],
      "partial": [],
      "expression_unique": [],
      "expression_indexes": [],
      "triggers": {},
      "grants": {},
      "unsupported": [
        "indexes"
      ],
      "privilege_denied": []
    },
    "target": {
      "table_type": null,
      "primary_key": [
        "id"
      ],
      "primary_key_informational": [],
      "unique": [
        [
          "code"
        ]
      ],
      "unique_nulls_equal": [],
      "foreign_keys": [],
      "foreign_keys_informational": [],
      "not_null": [
        "active_yn",
        "code",
        "id",
        "included_units",
        "monthly_fee",
        "overage_rate",
        "tier_cd"
      ],
      "indexes": [],
      "check_count": 0,
      "checks": [],
      "identity_columns": [],
      "partial": [],
      "expression_unique": [],
      "expression_indexes": [],
      "triggers": {},
      "grants": {},
      "unsupported": [],
      "privilege_denied": []
    },
    "identity": null
  },
  "tenants": {
    "source": {
      "table_type": null,
      "primary_key": [],
      "primary_key_informational": [],
      "unique": [],
      "unique_nulls_equal": [],
      "foreign_keys": [],
      "foreign_keys_informational": [],
      "not_null": [],
      "indexes": [],
      "check_count": 0,
      "checks": [],
      "identity_columns": [],
      "partial": [],
      "expression_unique": [],
      "expression_indexes": [],
      "triggers": {},
      "grants": {},
      "unsupported": [
        "indexes"
      ],
      "privilege_denied": []
    },
    "target": {
      "table_type": null,
      "primary_key": [
        "id"
      ],
      "primary_key_informational": [],
      "unique": [
        [
          "name"
        ]
      ],
      "unique_nulls_equal": [],
      "foreign_keys": [],
      "foreign_keys_informational": [],
      "not_null": [
        "id",
        "name",
        "status_cd",
        "tax_exempt_yn"
      ],
      "indexes": [],
      "check_count": 0,
      "checks": [],
      "identity_columns": [],
      "partial": [],
      "expression_unique": [],
      "expression_indexes": [],
      "triggers": {},
      "grants": {},
      "unsupported": [],
      "privilege_denied": []
    },
    "identity": null
  },
  "billing_audit_log": {
    "source": {
      "table_type": null,
      "primary_key": [],
      "primary_key_informational": [],
      "unique": [],
      "unique_nulls_equal": [],
      "foreign_keys": [],
      "foreign_keys_informational": [],
      "not_null": [],
      "indexes": [],
      "check_count": 0,
      "checks": [],
      "identity_columns": [],
      "partial": [],
      "expression_unique": [],
      "expression_indexes": [],
      "triggers": {},
      "grants": {},
      "unsupported": [
        "indexes"
      ],
      "privilege_denied": []
    },
    "target": {
      "table_type": null,
      "primary_key": [
        "log_id"
      ],
      "primary_key_informational": [],
      "unique": [],
      "unique_nulls_equal": [],
      "foreign_keys": [],
      "foreign_keys_informational": [],
      "not_null": [
        "log_id",
        "logged_at"
      ],
      "indexes": [],
      "check_count": 0,
      "checks": [],
      "identity_columns": [
        "log_id"
      ],
      "partial": [],
      "expression_unique": [],
      "expression_indexes": [],
      "triggers": {},
      "grants": {},
      "unsupported": [],
      "privilege_denied": []
    },
    "identity": null
  },
  "structural_checks": {
    "constraints": "checked",
    "triggers": "checked",
    "indexes": "unsupported",
    "sequences_identity": "checked",
    "grants": "direct_only"
  },
  "structural_diff": {
    "codes": {
      "constraints": [
        "source () -> expected (), target ('code_type', 'code_val')",
        "target code_desc is NOT NULL but its source column is nullable: legacy-valid NULLs would be rejected"
      ]
    },
    "plans": {
      "constraints": [
        "source () -> expected (), target ('id',)",
        "target unique ('code',) has no source counterpart: legacy-valid duplicates would be rejected",
        "target active_yn is NOT NULL but its source column is nullable: legacy-valid NULLs would be rejected",
        "target code is NOT NULL but its source column is nullable: legacy-valid NULLs would be rejected",
        "target included_units is NOT NULL but its source column is nullable: legacy-valid NULLs would be rejected",
        "target monthly_fee is NOT NULL but its source column is nullable: legacy-valid NULLs would be rejected",
        "target overage_rate is NOT NULL but its source column is nullable: legacy-valid NULLs would be rejected",
        "target tier_cd is NOT NULL but its source column is nullable: legacy-valid NULLs would be rejected"
      ]
    },
    "tenants": {
      "constraints": [
        "source () -> expected (), target ('id',)",
        "target unique ('name',) has no source counterpart: legacy-valid duplicates would be rejected",
        "target name is NOT NULL but its source column is nullable: legacy-valid NULLs would be rejected",
        "target status_cd is NOT NULL but its source column is nullable: legacy-valid NULLs would be rejected",
        "target tax_exempt_yn is NOT NULL but its source column is nullable: legacy-valid NULLs would be rejected"
      ]
    },
    "billing_audit_log": {
      "constraints": [
        "target logged_at is NOT NULL but its source column is nullable: legacy-valid NULLs would be rejected"
      ],
      "sequences_identity": [
        "target log_id is identity but source log_id is not: target-generated keys diverge from the source's"
      ]
    }
  },
  "platform_inherent": [],
  "dictionary": {
    "source": "live",
    "target": "live"
  }
}
```

## Tier 0 findings (17)
- `codes` primary_key_mismatch: source () -> expected (), target ('code_type', 'code_val')
- `codes` not_null_extra: target code_desc is NOT NULL but its source column is nullable: legacy-valid NULLs would be rejected
- `plans` primary_key_mismatch: source () -> expected (), target ('id',)
- `plans` unique_extra: target unique ('code',) has no source counterpart: legacy-valid duplicates would be rejected
- `plans` not_null_extra: target active_yn is NOT NULL but its source column is nullable: legacy-valid NULLs would be rejected
- `plans` not_null_extra: target code is NOT NULL but its source column is nullable: legacy-valid NULLs would be rejected
- `plans` not_null_extra: target included_units is NOT NULL but its source column is nullable: legacy-valid NULLs would be rejected
- `plans` not_null_extra: target monthly_fee is NOT NULL but its source column is nullable: legacy-valid NULLs would be rejected
- `plans` not_null_extra: target overage_rate is NOT NULL but its source column is nullable: legacy-valid NULLs would be rejected
- `plans` not_null_extra: target tier_cd is NOT NULL but its source column is nullable: legacy-valid NULLs would be rejected
- `tenants` primary_key_mismatch: source () -> expected (), target ('id',)
- `tenants` unique_extra: target unique ('name',) has no source counterpart: legacy-valid duplicates would be rejected
- `tenants` not_null_extra: target name is NOT NULL but its source column is nullable: legacy-valid NULLs would be rejected
- `tenants` not_null_extra: target status_cd is NOT NULL but its source column is nullable: legacy-valid NULLs would be rejected
- `tenants` not_null_extra: target tax_exempt_yn is NOT NULL but its source column is nullable: legacy-valid NULLs would be rejected
- `billing_audit_log` not_null_extra: target logged_at is NOT NULL but its source column is nullable: legacy-valid NULLs would be rejected
- `billing_audit_log` identity_extra: target log_id is identity but source log_id is not: target-generated keys diverge from the source's

## Tier 1 coverage
```json
{
  "source_counts": {
    "ow_tp.mig_unt19_20261030_src.CODES": 32,
    "ow_tp.mig_unt19_20261030_src.PLANS": 3,
    "ow_tp.mig_unt19_20261030_src.TENANTS": 70,
    "ow_tp.mig_unt19_20261030_src.BILLING_AUDIT_LOG": 0
  },
  "by_design_unverified": [
    "billing_audit_log"
  ]
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "codes.code_type",
    "codes.code_desc",
    "plans.id",
    "plans.code",
    "plans.active_yn",
    "tenants.id",
    "tenants.name",
    "tenants.tax_exempt_yn"
  ]
}
```

## Tier 3 coverage
```json
{
  "codes": {
    "mode": "full_diff",
    "population": 32,
    "null_key_rows": {
      "source": 0,
      "target": 0
    },
    "duplicate_source_key_count": 0
  },
  "plans": {
    "mode": "full_diff",
    "population": 3,
    "null_key_rows": {
      "source": 0,
      "target": 0
    },
    "duplicate_source_key_count": 0
  },
  "tenants": {
    "mode": "full_diff",
    "population": 70,
    "null_key_rows": {
      "source": 0,
      "target": 0
    },
    "duplicate_source_key_count": 0
  }
}
```
