# 04 — Model proposal review (s4.1-proposal, UNT8-11)

Review of the untouched proposer output `.migration/mapping_spec.json` (`version: map-draft-1`) on the run branch `tp-run/mongodb-20261007T161014Z`. This file becomes §1 of `05_decisions.md`; everything quoted below is copied from the generated JSON, nothing in the spec was hand-edited.

- Plugin: `Cognition-Partner-Workshops/mongo-migration-plugin` @ `353280fc837193a40ccc005cb62fb4ffaf8ac16f` (`~/mmp`, unpatched; `git status` clean at that SHA). Proposer: `skills/schema-modeling/model_proposal.py` + `model_relationships.py`; rule order and question families from `skills/schema-modeling/REFERENCE.md`.
- Command (run from the run-branch root, once):

  ```sh
  python3 ~/mmp/skills/schema-modeling/model_proposal.py \
    --census .migration/census.json --data-profile .migration/data_profile.json \
    --access-patterns .migration/access_patterns.json --ddl-census .migration/census_ddl.json \
    --out .migration/mapping_spec.json --version map-draft-1 --exclude-table FIXTURE_META
  ```

- Thresholds: defaults (`d-modeling-thresholds = default`) → `modeling.policy` = `{"max_doc_bytes": 2097152, "max_embed_fanout": 1000}` (2 MiB / 1000).
- Output `sha256 54d2e3173602e82f44a89ddc96cb1c67a4a31c7b98c89585b47f120a9e7713bb`. Inputs as recorded by the proposer: `data_profile` `{"path": ".migration/data_profile.json", "sha256": "f835faa57dfc1198f222911f8897c6a63337e998a81aee523a11c150bca86942", "as_of": "2026-10-07T16:49:28.839168+00:00"}`; `access_patterns` `{"path": ".migration/access_patterns.json", "sha256": "9440f5ca93aa5074859d1e75a0116b62920857d5d8b119b228b5fa0004d85ddc"}`; `ddl_census` `{"path": ".migration/census_ddl.json", "sha256": "b06e9a04b1b6abe937b52097eef63b940b04ddfc46dc6cead7c4a2c460295a30"}`.
- Previous run branch `tp-run/mongodb-20261007T062215Z` was not inspected (no `git show`/`log`/checkout/fetch-and-read of it).
- Legacy source (`services/legacy-billing/db/oracle/`, `testdata/legacy/oracle_billing_seed.py`) untouched. No database was used.

## 0. Result

| | value |
|---|---|
| collections | 16 (`ratingPeriods`, `customerMasterHist`, `invoices`, `codes`, `tenants`, `plans`, `subscriptions`, `usageEvents`, `notifications`, `customerMaster`, `entityAttrValue`, `invoiceHeader`, `invoiceLine`, `billingAuditLog`, `subscriptionsHist`, `ratingResults`) |
| embeds | 3 — `INVOICES` → `INVOICE_LINES` as `lines`; `INVOICES` → `DUNNING_ATTEMPTS` as `dunningAttempts`; `TENANTS` → `CREDIT_NOTES` as `creditNotes` |
| `modeling.rationale` rows | 23 — rules: `pointer_only_no_fk` ×10, `shared_child` ×7, `read_by_parent_key` ×2, `co_read` ×1, `child_written_alone` ×1, `lookup_reference` ×1, `default` ×1 |
| cardinality basis | `derived` 9, `assumed` 14 (§6) |
| collection `open_questions` | 42 — `code_lookup` ×11, `date_as_string` ×6, `unenforced_pointer` ×5, `pointer_unresolved` ×4, `csv_list` ×3, `repeating_group` ×2, `unrated_access_basis` ×2, `single_valued_index_key` ×2, `date_format_nonconforming` ×2, `pointer_target_suspect` ×2, `append_growth` ×1, `extended_reference_candidate` ×1, `polymorphic_pointer` ×1 |
| `modeling.unresolved` | 24 — `plsql_unit_needs_manual_review` ×10, `date_format_assumed` ×9, `trigger_business_logic` ×3, `scheduler_job` ×2 (§4) |
| `modeling.answered` | 9 (§5) |
| `modeling.excluded_tables` | `["FIXTURE_META"]` (§1) |
| `modeling.application_evidence.confirmed_patterns` | 64 over 12 files (§7) |
| literal `written_together` in the spec | no — the string does not occur anywhere in the file |
| literal `via_trigger` in the spec | no — the string does not occur anywhere in the file |
| `modeling.not_known_from_ddl` | `["semantics of triggers, packages, and scheduler jobs (names and targets only)"]` |

## 1. Excluded table: `FIXTURE_META`

The census lists 20 live tables; one is fixture bookkeeping and was excluded with `--exclude-table FIXTURE_META`. Census row: columns `["MARKER", "VALUE", "INITIALIZED_AT"]`, `primary_key` `[]`, `foreign_keys` `[]`, `row_estimate` 2. It is written only by the two `MERGE INTO fixture_meta` statements in `startup/00_init.sh` (`03_access_review.md` §3.16: "Roots not scanned … `startup/00_init.sh` (two `MERGE INTO fixture_meta`)") and no package, trigger, job or application statement reads it; it holds deploy markers, not billing data, so it is not a migration unit. The spec records it as:

```json
{
  "modeling.excluded_tables": [
    "FIXTURE_META"
  ]
}
```

No other table was excluded.

## 2. Requested tables and relationships

Conventions: *shape* is `decision.shape` of the owning collection (or the `embeds[].array_path` when embedded); *rule* is the `rule` field of the `modeling.rationale` row, named exactly as the proposer wrote it. `pointer_only_no_fk` is **not** one of the sixteen rules in the `REFERENCE.md` rule order — it is the DDL-only row `model_proposal.py` (`_pointer_only_rationales`) emits for every `unenforced_pointer` census trap before any relationship rule runs; such a pair never reached `child_is_parent` … `default` because the census has no relationship edge for it. Where a pair has **no** rationale row at all, that is stated.

### 2.1 `CUSTOMER_MASTER` → `customerMaster`

- **Shape:** own collection. `decision.shape` = `collection`, `key` `{"source": ["CUST_ID"], "target": "_id"}`, `key_strategy` = `natural primary key`, `embeds` = `[]`, `decision.references` = `[]`.
- **Rule(s) fired:** the only rationale row with `CUSTOMER_MASTER` as child is `TENANTS → CUSTOMER_MASTER` = `pointer_only_no_fk` / `reference` / `assumed`. As parent it appears in three rows (`CUSTOMER_MASTER_HIST`, `INVOICE_HEADER`, `INVOICE_LINE`), all `pointer_only_no_fk`. Nothing is embedded under it and it is embedded nowhere.
- **`rationale` rows (quoted):**

```json
{
  "parent": "TENANTS",
  "child": "CUSTOMER_MASTER",
  "child_columns": [
    "TENANT_ID"
  ],
  "rule": "pointer_only_no_fk",
  "decision": "reference",
  "basis": "assumed",
  "basis_sources": [
    "ddl"
  ],
  "evidence": [
    {
      "kind": "ddl",
      "ref": "*_ID column with a matching table and no FK"
    }
  ]
}
```
```json
{
  "parent": "CUSTOMER_MASTER",
  "child": "CUSTOMER_MASTER_HIST",
  "child_columns": [
    "CUST_ID"
  ],
  "rule": "pointer_only_no_fk",
  "decision": "reference",
  "basis": "assumed",
  "basis_sources": [
    "ddl"
  ],
  "evidence": [
    {
      "kind": "ddl",
      "ref": "*_ID column with a matching table and no FK"
    }
  ]
}
```
```json
{
  "parent": "CUSTOMER_MASTER",
  "child": "INVOICE_HEADER",
  "child_columns": [
    "CUST_ID"
  ],
  "rule": "pointer_only_no_fk",
  "decision": "reference",
  "basis": "assumed",
  "basis_sources": [
    "ddl"
  ],
  "evidence": [
    {
      "kind": "ddl",
      "ref": "*_ID column with a matching table and no FK"
    }
  ]
}
```
```json
{
  "parent": "CUSTOMER_MASTER",
  "child": "INVOICE_LINE",
  "child_columns": [
    "CUST_ID"
  ],
  "rule": "pointer_only_no_fk",
  "decision": "reference",
  "basis": "assumed",
  "basis_sources": [
    "ddl"
  ],
  "evidence": [
    {
      "kind": "ddl",
      "ref": "*_ID column with a matching table and no FK"
    }
  ]
}
```

- **`open_questions` by kind** (7 items; the packed/CSV/dirty-date columns are covered here and in §2.5):

- **`date_format_nonconforming`**

```json
{
  "kind": "date_format_nonconforming",
  "table": "CUSTOMER_MASTER",
  "column": "SIGNUP_DT",
  "measured_format": "%d-%b-%y",
  "conformance": 0.845771,
  "rows_shaped": 201,
  "est_bad_rows": 32,
  "evidence": {
    "kind": "data_profile",
    "ref": "text_shapes:CUSTOMER_MASTER.SIGNUP_DT"
  },
  "proposal": "quarantine approximately 32 rows that do not match '%d-%b-%y' before converting CUSTOMER_MASTER.SIGNUP_DT; confirm the bad-row handling policy"
}
```

- **`repeating_group`**

```json
{
  "kind": "repeating_group",
  "table": "CUSTOMER_MASTER",
  "evidence": "numbered column series; candidate arrays",
  "groups": {
    "ADDR_LINE": [
      "ADDR_LINE_1",
      "ADDR_LINE_2",
      "ADDR_LINE_3",
      "ADDR_LINE_4",
      "ADDR_LINE_5",
      "ADDR_LINE_6"
    ],
    "MAIL_ADDR_LINE": [
      "MAIL_ADDR_LINE_1",
      "MAIL_ADDR_LINE_2",
      "MAIL_ADDR_LINE_3",
      "MAIL_ADDR_LINE_4",
      "MAIL_ADDR_LINE_5",
      "MAIL_ADDR_LINE_6"
    ],
    "PHONE": [
      "PHONE1",
      "PHONE2",
      "PHONE3",
      "PHONE4"
    ],
    "EMAIL": [
      "EMAIL_1",
      "EMAIL_2",
      "EMAIL_3"
    ],
    "FLAG": [
      "FLAG_01",
      "FLAG_02",
      "FLAG_03",
      "FLAG_04",
      "FLAG_05",
      "FLAG_06",
      "FLAG_07",
      "FLAG_08",
      "FLAG_09",
      "FLAG_10",
      "FLAG_11",
      "FLAG_12",
      "FLAG_13",
      "FLAG_14",
      "FLAG_15",
      "FLAG_16",
      "FLAG_17",
      "FLAG_18",
      "FLAG_19",
      "FLAG_20"
    ],
    "UDF": [
      "UDF_01",
      "UDF_02",
      "UDF_03",
      "UDF_04",
      "UDF_05",
      "UDF_06",
      "UDF_07",
      "UDF_08",
      "UDF_09",
      "UDF_10",
      "UDF_11",
      "UDF_12",
      "UDF_13",
      "UDF_14",
      "UDF_15",
      "UDF_16",
      "UDF_17",
      "UDF_18",
      "UDF_19",
      "UDF_20",
      "UDF_21",
      "UDF_22",
      "UDF_23",
      "UDF_24",
      "UDF_25",
      "UDF_26",
      "UDF_27",
      "UDF_28",
      "UDF_29",
      "UDF_30",
      "UDF_31",
      "UDF_32",
      "UDF_33",
      "UDF_34",
      "UDF_35",
      "UDF_36",
      "UDF_37",
      "UDF_38",
      "UDF_39",
      "UDF_40"
    ],
    "UDF_AMT": [
      "UDF_AMT_01",
      "UDF_AMT_02",
      "UDF_AMT_03",
      "UDF_AMT_04",
      "UDF_AMT_05",
      "UDF_AMT_06",
      "UDF_AMT_07",
      "UDF_AMT_08",
      "UDF_AMT_09",
      "UDF_AMT_10"
    ],
    "UDF_DT": [
      "UDF_DT_01",
      "UDF_DT_02",
      "UDF_DT_03",
      "UDF_DT_04",
      "UDF_DT_05",
      "UDF_DT_06",
      "UDF_DT_07",
      "UDF_DT_08",
      "UDF_DT_09",
      "UDF_DT_10"
    ]
  },
  "proposal": "collapse each numbered series into one array field; needs app evidence, mapped 1:1 until then"
}
```

- **`unenforced_pointer`**

```json
{
  "kind": "unenforced_pointer",
  "table": "CUSTOMER_MASTER",
  "evidence": "*_ID column with a matching table and no FK",
  "columns": [
    "TENANT_ID"
  ],
  "targets": [
    "TENANTS"
  ],
  "target_basis": [
    "table_name"
  ],
  "proposal": "treat as reference; verify pointer resolves before embedding anything"
}
```

- **`code_lookup`**

```json
{
  "kind": "code_lookup",
  "table": "CUSTOMER_MASTER",
  "evidence": [
    {
      "kind": "data_profile",
      "ref": "value_domain:CUSTOMER_MASTER.PHONE1_TYPE_CD"
    },
    {
      "kind": "data_profile",
      "ref": "value_domain:CUSTOMER_MASTER.PHONE2_TYPE_CD"
    },
    {
      "kind": "data_profile",
      "ref": "value_domain:CUSTOMER_MASTER.PHONE3_TYPE_CD"
    },
    {
      "kind": "data_profile",
      "ref": "value_domain:CUSTOMER_MASTER.PHONE4_TYPE_CD"
    },
    {
      "kind": "data_profile",
      "ref": "value_domain:CUSTOMER_MASTER.STATUS_CD"
    },
    {
      "kind": "data_profile",
      "ref": "value_domain:CUSTOMER_MASTER.SUB_STATUS_CD"
    },
    {
      "kind": "data_profile",
      "ref": "value_domain:CUSTOMER_MASTER.CUST_TYPE_CD"
    },
    {
      "kind": "data_profile",
      "ref": "value_domain:CUSTOMER_MASTER.SEGMENT_CD"
    },
    {
      "kind": "data_profile",
      "ref": "value_domain:CUSTOMER_MASTER.REGION_CD"
    },
    {
      "kind": "data_profile",
      "ref": "value_domain:CUSTOMER_MASTER.TERRITORY_CD"
    },
    {
      "kind": "data_profile",
      "ref": "value_domain:CUSTOMER_MASTER.CHANNEL_CD"
    },
    {
      "kind": "data_profile",
      "ref": "value_domain:CUSTOMER_MASTER.RATE_CLASS_CD"
    },
    {
      "kind": "data_profile",
      "ref": "code_resolve:CUSTOMER_MASTER.PHONE1_TYPE_CD"
    },
    {
      "kind": "data_profile",
      "ref": "code_resolve:CUSTOMER_MASTER.PHONE2_TYPE_CD"
    },
    {
      "kind": "data_profile",
      "ref": "code_resolve:CUSTOMER_MASTER.PHONE3_TYPE_CD"
    },
    {
      "kind": "data_profile",
      "ref": "code_resolve:CUSTOMER_MASTER.PHONE4_TYPE_CD"
    },
    {
      "kind": "data_profile",
      "ref": "code_resolve:CUSTOMER_MASTER.STATUS_CD"
    },
    {
      "kind": "data_profile",
      "ref": "code_resolve:CUSTOMER_MASTER.SUB_STATUS_CD"
    },
    {
      "kind": "data_profile",
      "ref": "code_resolve:CUSTOMER_MASTER.CUST_TYPE_CD"
    },
    {
      "kind": "data_profile",
      "ref": "code_resolve:CUSTOMER_MASTER.SEGMENT_CD"
    },
    {
      "kind": "data_profile",
      "ref": "code_resolve:CUSTOMER_MASTER.REGION_CD"
    },
    {
      "kind": "data_profile",
      "ref": "code_resolve:CUSTOMER_MASTER.TERRITORY_CD"
    },
    {
      "kind": "data_profile",
      "ref": "code_resolve:CUSTOMER_MASTER.CHANNEL_CD"
    },
    {
      "kind": "data_profile",
      "ref": "code_resolve:CUSTOMER_MASTER.RATE_CLASS_CD"
    }
  ],
  "columns": [
    "PHONE1_TYPE_CD",
    "PHONE2_TYPE_CD",
    "PHONE3_TYPE_CD",
    "PHONE4_TYPE_CD",
    "STATUS_CD",
    "SUB_STATUS_CD",
    "CUST_TYPE_CD",
    "SEGMENT_CD",
    "REGION_CD",
    "TERRITORY_CD",
    "CHANNEL_CD",
    "RATE_CLASS_CD"
  ],
  "proposal": "keep the numeric code and denormalize the label from the codes table: STATUS_CD -> CUST_STATUS. ambiguous: PHONE1_TYPE_CD: CUST_STATUS, CUST_TYPE, NOTIF_KIND, PHONE_TYPE, PLAN_TIER, USAGE_KIND all cover the domain; the app or a type column must say which; PHONE2_TYPE_CD: CUST_STATUS, CUST_TYPE, NOTIF_KIND, PHONE_TYPE, PLAN_TIER, USAGE_KIND all cover the domain; the app or a type column must say which; SUB_STATUS_CD: CUST_STATUS, CUST_TYPE, NOTIF_KIND, PHONE_TYPE, PLAN_TIER, USAGE_KIND all cover the domain; the app or a type column must say which; CUST_TYPE_CD: CUST_STATUS, CUST_TYPE, NOTIF_KIND, PHONE_TYPE, PLAN_TIER, USAGE_KIND all cover the domain; the app or a type column must say which; SEGMENT_CD: no single code type covers every value (PHONE_TYPE, CUST_STATUS, CUST_TYPE, NOTIF_KIND); REGION_CD: no single code type covers every value (PHONE_TYPE, CUST_STATUS, CUST_TYPE, NOTIF_KIND). unresolved: SEGMENT_CD: 5 value(s) in 101 row(s) match no code type; REGION_CD: 7 value(s) in 111 row(s) match no code type -> keep the raw code and do not fail the load on a missing label",
  "measurements": {
    "PHONE1_TYPE_CD": {
      "distinct_values": 1,
      "null_count": 0,
      "code_resolution": {
        "distinct_values": 1,
        "candidates": [
          {
            "code_type": "CUST_STATUS",
            "distinct_values": 1,
            "rows": 201
          },
          {
            "code_type": "CUST_TYPE",
            "distinct_values": 1,
            "rows": 201
          },
          {
            "code_type": "NOTIF_KIND",
            "distinct_values": 1,
            "rows": 201
          },
          {
            "code_type": "PHONE_TYPE",
            "distinct_values": 1,
            "rows": 201
          },
          {
            "code_type": "PLAN_TIER",
            "distinct_values": 1,
            "rows": 201
          },
          {
            "code_type": "USAGE_KIND",
            "distinct_values": 1,
            "rows": 201
          }
        ],
        "full_cover": [
          "CUST_STATUS",
          "CUST_TYPE",
          "NOTIF_KIND",
          "PHONE_TYPE",
          "PLAN_TIER",
          "USAGE_KIND"
        ],
        "unresolved_distinct": 0,
        "unresolved_rows": 0,
        "unresolved_values": []
      }
    },
    "PHONE2_TYPE_CD": {
      "distinct_values": 1,
      "null_count": 1,
      "code_resolution": {
        "distinct_values": 1,
        "candidates": [
          {
            "code_type": "CUST_STATUS",
            "distinct_values": 1,
            "rows": 200
          },
          {
            "code_type": "CUST_TYPE",
            "distinct_values": 1,
            "rows": 200
          },
          {
            "code_type": "NOTIF_KIND",
            "distinct_values": 1,
            "rows": 200
          },
          {
            "code_type": "PHONE_TYPE",
            "distinct_values": 1,
            "rows": 200
          },
          {
            "code_type": "PLAN_TIER",
            "distinct_values": 1,
            "rows": 200
          },
          {
            "code_type": "USAGE_KIND",
            "distinct_values": 1,
            "rows": 200
          }
        ],
        "full_cover": [
          "CUST_STATUS",
          "CUST_TYPE",
          "NOTIF_KIND",
          "PHONE_TYPE",
          "PLAN_TIER",
          "USAGE_KIND"
        ],
        "unresolved_distinct": 0,
        "unresolved_rows": 0,
        "unresolved_values": []
      }
    },
    "PHONE3_TYPE_CD": {
      "distinct_values": 0,
      "null_count": 201,
      "code_resolution": {
        "distinct_values": 0,
        "candidates": [],
        "full_cover": [],
        "unresolved_distinct": 0,
        "unresolved_rows": 0,
        "unresolved_values": []
      }
    },
    "PHONE4_TYPE_CD": {
      "distinct_values": 0,
      "null_count": 201,
      "code_resolution": {
        "distinct_values": 0,
        "candidates": [],
        "full_cover": [],
        "unresolved_distinct": 0,
        "unresolved_rows": 0,
        "unresolved_values": []
      }
    },
    "STATUS_CD": {
      "distinct_values": 4,
      "null_count": 0,
      "code_resolution": {
        "distinct_values": 4,
        "candidates": [
          {
            "code_type": "CUST_STATUS",
            "distinct_values": 4,
            "rows": 201
          },
          {
            "code_type": "CUST_TYPE",
            "distinct_values": 3,
            "rows": 199
          },
          {
            "code_type": "NOTIF_KIND",
            "distinct_values": 3,
            "rows": 199
          },
          {
            "code_type": "PHONE_TYPE",
            "distinct_values": 3,
            "rows": 199
          },
          {
            "code_type": "PLAN_TIER",
            "distinct_values": 3,
            "rows": 199
          },
          {
            "code_type": "USAGE_KIND",
            "distinct_values": 3,
            "rows": 199
          }
        ],
        "full_cover": [
          "CUST_STATUS"
        ],
        "unresolved_distinct": 0,
        "unresolved_rows": 0,
        "unresolved_values": []
      }
    },
    "SUB_STATUS_CD": {
      "distinct_values": 2,
      "null_count": 66,
      "code_resolution": {
        "distinct_values": 2,
        "candidates": [
          {
            "code_type": "CUST_STATUS",
            "distinct_values": 2,
            "rows": 135
          },
          {
            "code_type": "CUST_TYPE",
            "distinct_values": 2,
            "rows": 135
          },
          {
            "code_type": "NOTIF_KIND",
            "distinct_values": 2,
            "rows": 135
          },
          {
            "code_type": "PHONE_TYPE",
            "distinct_values": 2,
            "rows": 135
          },
          {
            "code_type": "PLAN_TIER",
            "distinct_values": 2,
            "rows": 135
          },
          {
            "code_type": "USAGE_KIND",
            "distinct_values": 2,
            "rows": 135
          }
        ],
        "full_cover": [
          "CUST_STATUS",
          "CUST_TYPE",
          "NOTIF_KIND",
          "PHONE_TYPE",
          "PLAN_TIER",
          "USAGE_KIND"
        ],
        "unresolved_distinct": 0,
        "unresolved_rows": 0,
        "unresolved_values": []
      }
    },
    "CUST_TYPE_CD": {
      "distinct_values": 3,
      "null_count": 0,
      "code_resolution": {
        "distinct_values": 3,
        "candidates": [
          {
            "code_type": "CUST_STATUS",
            "distinct_values": 3,
            "rows": 201
          },
          {
            "code_type": "CUST_TYPE",
            "distinct_values": 3,
            "rows": 201
          },
          {
            "code_type": "NOTIF_KIND",
            "distinct_values": 3,
            "rows": 201
          },
          {
            "code_type": "PHONE_TYPE",
            "distinct_values": 3,
            "rows": 201
          },
          {
            "code_type": "PLAN_TIER",
            "distinct_values": 3,
            "rows": 201
          },
          {
            "code_type": "USAGE_KIND",
            "distinct_values": 3,
            "rows": 201
          }
        ],
        "full_cover": [
          "CUST_STATUS",
          "CUST_TYPE",
          "NOTIF_KIND",
          "PHONE_TYPE",
          "PLAN_TIER",
          "USAGE_KIND"
        ],
        "unresolved_distinct": 0,
        "unresolved_rows": 0,
        "unresolved_values": []
      }
    },
    "SEGMENT_CD": {
      "distinct_values": 9,
      "null_count": 0,
      "code_resolution": {
        "distinct_values": 9,
        "candidates": [
          {
            "code_type": "PHONE_TYPE",
            "distinct_values": 4,
            "rows": 100
          },
          {
            "code_type": "CUST_STATUS",
            "distinct_values": 3,
            "rows": 74
          },
          {
            "code_type": "CUST_TYPE",
            "distinct_values": 3,
            "rows": 74
          },
          {
            "code_type": "NOTIF_KIND",
            "distinct_values": 3,
            "rows": 74
          },
          {
            "code_type": "PLAN_TIER",
            "distinct_values": 3,
            "rows": 74
          },
          {
            "code_type": "USAGE_KIND",
            "distinct_values": 3,
            "rows": 74
          }
        ],
        "full_cover": [],
        "unresolved_distinct": 5,
        "unresolved_rows": 101,
        "unresolved_values": [
          [
            8,
            32
          ],
          [
            6,
            21
          ],
          [
            7,
            20
          ],
          [
            5,
            14
          ],
          [
            9,
            14
          ]
        ]
      }
    },
    "REGION_CD": {
      "distinct_values": 12,
      "null_count": 0,
      "code_resolution": {
        "distinct_values": 12,
        "candidates": [
          {
            "code_type": "PHONE_TYPE",
            "distinct_values": 4,
            "rows": 73
          },
          {
            "code_type": "CUST_STATUS",
            "distinct_values": 3,
            "rows": 54
          },
          {
            "code_type": "CUST_TYPE",
            "distinct_values": 3,
            "rows": 54
          },
          {
            "code_type": "NOTIF_KIND",
            "distinct_values": 3,
            "rows": 54
          },
          {
            "code_type": "PLAN_TIER",
            "distinct_values": 3,
            "rows": 54
          },
          {
            "code_type": "USAGE_KIND",
            "distinct_values": 3,
            "rows": 54
          },
          {
            "code_type": "DUN_STATUS",
            "distinct_values": 1,
            "rows": 17
          },
          {
            "code_type": "INV_STATUS",
            "distinct_values": 1,
            "rows": 17
          },
          {
            "code_type": "SUB_STATUS",
            "distinct_values": 1,
            "rows": 17
          },
          {
            "code_type": "TENANT_STATUS",
            "distinct_values": 1,
            "rows": 17
          }
        ],
        "full_cover": [],
        "unresolved_distinct": 7,
        "unresolved_rows": 111,
        "unresolved_values": [
          [
            11,
            22
          ],
          [
            8,
            18
          ],
          [
            12,
            17
          ],
          [
            9,
            17
          ],
          [
            6,
            16
          ],
          [
            5,
            11
          ],
          [
            7,
            10
          ]
        ]
      }
    },
    "TERRITORY_CD": {
      "distinct_values": 0,
      "null_count": 201,
      "code_resolution": {
        "distinct_values": 0,
        "candidates": [],
        "full_cover": [],
        "unresolved_distinct": 0,
        "unresolved_rows": 0,
        "unresolved_values": []
      }
    },
    "CHANNEL_CD": {
      "distinct_values": 0,
      "null_count": 201,
      "code_resolution": {
        "distinct_values": 0,
        "candidates": [],
        "full_cover": [],
        "unresolved_distinct": 0,
        "unresolved_rows": 0,
        "unresolved_values": []
      }
    },
    "RATE_CLASS_CD": {
      "distinct_values": 0,
      "null_count": 201,
      "code_resolution": {
        "distinct_values": 0,
        "candidates": [],
        "full_cover": [],
        "unresolved_distinct": 0,
        "unresolved_rows": 0,
        "unresolved_values": []
      }
    }
  }
}
```

- **`date_as_string`**

```json
{
  "kind": "date_as_string",
  "table": "CUSTOMER_MASTER",
  "evidence": "date kept as text",
  "columns": [
    "SIGNUP_DT",
    "LAST_ACTIVITY_DT",
    "LAST_INVOICE_DT",
    "LAST_PAYMENT_DT",
    "TERMINATE_DT"
  ]
}
```

- **`csv_list`**

```json
{
  "kind": "csv_list",
  "table": "CUSTOMER_MASTER",
  "evidence": [
    {
      "kind": "data_profile",
      "ref": "csv_elements:CUSTOMER_MASTER.RELATED_ACCT_IDS"
    },
    {
      "kind": "data_profile",
      "ref": "csv_elements:CUSTOMER_MASTER.CHILD_ACCT_IDS"
    },
    {
      "kind": "data_profile",
      "ref": "csv_elements:CUSTOMER_MASTER.PROMO_CODES_CSV"
    }
  ],
  "columns": [
    "RELATED_ACCT_IDS",
    "CHILD_ACCT_IDS",
    "PROMO_CODES_CSV"
  ],
  "measurements": {
    "RELATED_ACCT_IDS": {
      "max_elements": 4.0,
      "avg_elements": 2.59375
    },
    "CHILD_ACCT_IDS": {
      "max_elements": null,
      "avg_elements": null
    },
    "PROMO_CODES_CSV": {
      "max_elements": 2.0,
      "avg_elements": 1.475177304964539
    }
  }
}
```

- **`pointer_unresolved`**

```json
{
  "kind": "pointer_unresolved",
  "table": "CUSTOMER_MASTER",
  "column": "TENANT_ID",
  "target": "TENANTS",
  "non_null": 201,
  "unresolved": 200,
  "evidence": {
    "kind": "data_profile",
    "ref": "pointer_resolve:CUSTOMER_MASTER.TENANT_ID->TENANTS"
  },
  "proposal": "some pointer rows do not resolve; decide orphan handling before embedding"
}
```

- **Index candidates:**

```json
[
  {
    "keys": [
      [
        "tenantId",
        1
      ],
      [
        "custSeqNo",
        1
      ]
    ],
    "origin": "access",
    "evidence": [
      {
        "kind": "access_pattern",
        "ref": "ap-bd510b9356"
      },
      {
        "kind": "access_pattern",
        "ref": "ap-e45fe9768e"
      }
    ]
  }
]
```

  Both cited patterns are application reads (`ap-bd510b9356`, `ap-e45fe9768e` → `services/legacy-billing/app/facade.py`); no package touches `CUSTOMER_MASTER`.
- **Package evidence:** none — `03_access_review.md` check 2 and §3 consequences: "INVOICE_HEADER / INVOICE_LINE / CUSTOMER_MASTER (CUSTBILL estate): reads only, batch-scoped, no edges". The proposer agrees: every row is `basis_sources: ["ddl"]`.
- **Contradictions with `03_access_review.md`:** none on shape. Note that `pointer_unresolved` reports `TENANT_ID` 200 of 201 unresolved against `TENANTS`, consistent with the review's reading that the CUSTBILL estate is not tenant-joined; the review did not predict a rule name for this table.

### 2.2 `INVOICE_HEADER` → `INVOICE_LINE` (and the pointer from `CUSTOMER_MASTER`)

- **Shape:** two own collections, referenced. `invoiceHeader`: `key` `{"source": ["INVOICE_ID"], "target": "_id"}`, `key_strategy` = `natural primary key`, `embeds` = `[]`. `invoiceLine`: `key` `{"source": ["LINE_ID"], "target": "_id"}`, `key_strategy` = `natural primary key`, `embeds` = `[]`. `INVOICE_LINE` is **not** embedded under `INVOICE_HEADER`.
- **Rule fired:** `INVOICE_HEADER → INVOICE_LINE` = `pointer_only_no_fk` / `reference` / `assumed`; `CUSTOMER_MASTER → INVOICE_HEADER`, `CUSTOMER_MASTER → INVOICE_LINE`, `TENANTS → INVOICE_HEADER`, `TENANTS → INVOICE_LINE` likewise. No relationship rule from the `REFERENCE.md` order ran for any of these pairs (no census edge).
- **`rationale` rows (quoted):**

```json
{
  "parent": "CUSTOMER_MASTER",
  "child": "INVOICE_HEADER",
  "child_columns": [
    "CUST_ID"
  ],
  "rule": "pointer_only_no_fk",
  "decision": "reference",
  "basis": "assumed",
  "basis_sources": [
    "ddl"
  ],
  "evidence": [
    {
      "kind": "ddl",
      "ref": "*_ID column with a matching table and no FK"
    }
  ]
}
```
```json
{
  "parent": "TENANTS",
  "child": "INVOICE_HEADER",
  "child_columns": [
    "TENANT_ID"
  ],
  "rule": "pointer_only_no_fk",
  "decision": "reference",
  "basis": "assumed",
  "basis_sources": [
    "ddl"
  ],
  "evidence": [
    {
      "kind": "ddl",
      "ref": "*_ID column with a matching table and no FK"
    }
  ]
}
```
```json
{
  "parent": "INVOICE_HEADER",
  "child": "INVOICE_LINE",
  "child_columns": [
    "INVOICE_ID"
  ],
  "rule": "pointer_only_no_fk",
  "decision": "reference",
  "basis": "assumed",
  "basis_sources": [
    "ddl"
  ],
  "evidence": [
    {
      "kind": "ddl",
      "ref": "*_ID column with a matching table and no FK"
    }
  ]
}
```
```json
{
  "parent": "CUSTOMER_MASTER",
  "child": "INVOICE_LINE",
  "child_columns": [
    "CUST_ID"
  ],
  "rule": "pointer_only_no_fk",
  "decision": "reference",
  "basis": "assumed",
  "basis_sources": [
    "ddl"
  ],
  "evidence": [
    {
      "kind": "ddl",
      "ref": "*_ID column with a matching table and no FK"
    }
  ]
}
```
```json
{
  "parent": "TENANTS",
  "child": "INVOICE_LINE",
  "child_columns": [
    "TENANT_ID"
  ],
  "rule": "pointer_only_no_fk",
  "decision": "reference",
  "basis": "assumed",
  "basis_sources": [
    "ddl"
  ],
  "evidence": [
    {
      "kind": "ddl",
      "ref": "*_ID column with a matching table and no FK"
    }
  ]
}
```

- **`open_questions` — `INVOICE_HEADER`:**

- **`unenforced_pointer`**

```json
{
  "kind": "unenforced_pointer",
  "table": "INVOICE_HEADER",
  "evidence": [
    {
      "kind": "ddl",
      "ref": "*_ID column with a matching table and no FK"
    },
    {
      "kind": "data_profile",
      "ref": "pointer_resolve:INVOICE_HEADER.CUST_ID->CUSTOMER_MASTER"
    }
  ],
  "columns": [
    "CUST_ID",
    "TENANT_ID"
  ],
  "targets": [
    "CUSTOMER_MASTER",
    "TENANTS"
  ],
  "target_basis": [
    "pk_column",
    "table_name"
  ],
  "proposal": "all profiled values resolve: model as a reference and enforce it in the application",
  "measured": {
    "resolve_rate": 1.0
  }
}
```

- **`code_lookup`**

```json
{
  "kind": "code_lookup",
  "table": "INVOICE_HEADER",
  "evidence": [
    {
      "kind": "data_profile",
      "ref": "value_domain:INVOICE_HEADER.STATUS_CD"
    },
    {
      "kind": "data_profile",
      "ref": "code_resolve:INVOICE_HEADER.STATUS_CD"
    }
  ],
  "columns": [
    "STATUS_CD"
  ],
  "proposal": "keep the numeric code and denormalize the label from the codes table: STATUS_CD -> INV_STATUS",
  "measurements": {
    "STATUS_CD": {
      "distinct_values": 3,
      "null_count": 0,
      "code_resolution": {
        "distinct_values": 3,
        "candidates": [
          {
            "code_type": "INV_STATUS",
            "distinct_values": 3,
            "rows": 1000
          },
          {
            "code_type": "DUN_STATUS",
            "distinct_values": 2,
            "rows": 850
          },
          {
            "code_type": "SUB_STATUS",
            "distinct_values": 2,
            "rows": 850
          },
          {
            "code_type": "TENANT_STATUS",
            "distinct_values": 1,
            "rows": 309
          }
        ],
        "full_cover": [
          "INV_STATUS"
        ],
        "unresolved_distinct": 0,
        "unresolved_rows": 0,
        "unresolved_values": []
      }
    }
  }
}
```

- **`date_as_string`**

```json
{
  "kind": "date_as_string",
  "table": "INVOICE_HEADER",
  "evidence": "date kept as text",
  "columns": [
    "INVOICE_DT",
    "DUE_DT"
  ]
}
```

- **`pointer_target_suspect`**

```json
{
  "kind": "pointer_target_suspect",
  "table": "INVOICE_HEADER",
  "column": "TENANT_ID",
  "target": "TENANTS",
  "alternatives": [],
  "resolve_rate": 0.0,
  "evidence": {
    "kind": "data_profile",
    "ref": "pointer_resolve:INVOICE_HEADER.TENANT_ID->TENANTS"
  },
  "proposal": "no profiled TENANT_ID values resolve to TENANTS; verify the target against other primary-key columns in the census before treating the pointer as unresolved"
}
```

- **`pointer_unresolved`**

```json
{
  "kind": "pointer_unresolved",
  "table": "INVOICE_HEADER",
  "column": "TENANT_ID",
  "target": "TENANTS",
  "non_null": 1000,
  "unresolved": 1000,
  "evidence": {
    "kind": "data_profile",
    "ref": "pointer_resolve:INVOICE_HEADER.TENANT_ID->TENANTS"
  },
  "proposal": "some pointer rows do not resolve; decide orphan handling before embedding"
}
```

- **`open_questions` — `INVOICE_LINE`:**

- **`unenforced_pointer`**

```json
{
  "kind": "unenforced_pointer",
  "table": "INVOICE_LINE",
  "evidence": [
    {
      "kind": "ddl",
      "ref": "*_ID column with a matching table and no FK"
    },
    {
      "kind": "data_profile",
      "ref": "pointer_resolve:INVOICE_LINE.CUST_ID->CUSTOMER_MASTER"
    }
  ],
  "columns": [
    "INVOICE_ID",
    "CUST_ID",
    "TENANT_ID"
  ],
  "targets": [
    "INVOICE_HEADER",
    "CUSTOMER_MASTER",
    "TENANTS"
  ],
  "target_basis": [
    "pk_column",
    "pk_column",
    "table_name"
  ],
  "target_alternatives": [
    [
      "INVOICES"
    ],
    [],
    []
  ],
  "proposal": "all profiled values resolve: model as a reference and enforce it in the application",
  "measured": {
    "resolve_rate": 1.0
  }
}
```

- **`code_lookup`**

```json
{
  "kind": "code_lookup",
  "table": "INVOICE_LINE",
  "evidence": [
    {
      "kind": "data_profile",
      "ref": "value_domain:INVOICE_LINE.LINE_TYPE_CD"
    },
    {
      "kind": "data_profile",
      "ref": "code_resolve:INVOICE_LINE.LINE_TYPE_CD"
    }
  ],
  "columns": [
    "LINE_TYPE_CD"
  ],
  "proposal": "ambiguous: LINE_TYPE_CD: no single code type covers every value (CUST_STATUS, CUST_TYPE, NOTIF_KIND, PHONE_TYPE). unresolved: LINE_TYPE_CD: 1 value(s) in 256 row(s) match no code type -> keep the raw code and do not fail the load on a missing label",
  "measurements": {
    "LINE_TYPE_CD": {
      "distinct_values": 4,
      "null_count": 0,
      "code_resolution": {
        "distinct_values": 4,
        "candidates": [
          {
            "code_type": "CUST_STATUS",
            "distinct_values": 3,
            "rows": 1244
          },
          {
            "code_type": "CUST_TYPE",
            "distinct_values": 3,
            "rows": 1244
          },
          {
            "code_type": "NOTIF_KIND",
            "distinct_values": 3,
            "rows": 1244
          },
          {
            "code_type": "PHONE_TYPE",
            "distinct_values": 3,
            "rows": 1244
          },
          {
            "code_type": "PLAN_TIER",
            "distinct_values": 3,
            "rows": 1244
          },
          {
            "code_type": "USAGE_KIND",
            "distinct_values": 3,
            "rows": 1244
          }
        ],
        "full_cover": [],
        "unresolved_distinct": 1,
        "unresolved_rows": 256,
        "unresolved_values": [
          [
            9,
            256
          ]
        ]
      }
    }
  }
}
```

- **`date_as_string`**

```json
{
  "kind": "date_as_string",
  "table": "INVOICE_LINE",
  "evidence": "date kept as text",
  "columns": [
    "INVOICE_DT"
  ]
}
```

- **`csv_list`**

```json
{
  "kind": "csv_list",
  "table": "INVOICE_LINE",
  "evidence": [
    {
      "kind": "data_profile",
      "ref": "csv_elements:INVOICE_LINE.GL_ACCT_CSV"
    }
  ],
  "columns": [
    "GL_ACCT_CSV"
  ],
  "measurements": {
    "GL_ACCT_CSV": {
      "max_elements": 3.0,
      "avg_elements": 2.042
    }
  }
}
```

- **`pointer_unresolved`**

```json
{
  "kind": "pointer_unresolved",
  "table": "INVOICE_LINE",
  "column": "INVOICE_ID",
  "target": "INVOICE_HEADER",
  "non_null": 1500,
  "unresolved": 37,
  "evidence": {
    "kind": "data_profile",
    "ref": "pointer_resolve:INVOICE_LINE.INVOICE_ID->INVOICE_HEADER"
  },
  "proposal": "some pointer rows do not resolve; decide orphan handling before embedding"
}
```

- **`pointer_target_suspect`**

```json
{
  "kind": "pointer_target_suspect",
  "table": "INVOICE_LINE",
  "column": "TENANT_ID",
  "target": "TENANTS",
  "alternatives": [],
  "resolve_rate": 0.0,
  "evidence": {
    "kind": "data_profile",
    "ref": "pointer_resolve:INVOICE_LINE.TENANT_ID->TENANTS"
  },
  "proposal": "no profiled TENANT_ID values resolve to TENANTS; verify the target against other primary-key columns in the census before treating the pointer as unresolved"
}
```

- **`pointer_unresolved`**

```json
{
  "kind": "pointer_unresolved",
  "table": "INVOICE_LINE",
  "column": "TENANT_ID",
  "target": "TENANTS",
  "non_null": 1500,
  "unresolved": 1500,
  "evidence": {
    "kind": "data_profile",
    "ref": "pointer_resolve:INVOICE_LINE.TENANT_ID->TENANTS"
  },
  "proposal": "some pointer rows do not resolve; decide orphan handling before embedding"
}
```

- **Index candidates:** `invoiceHeader.indexes` = `[]`, `invoiceLine.indexes` = `[]`. The batch-report read `ap-89c88ad4c6` (`INVOICE_HEADER.BATCH_NO eq`, `CODES.CODE_TYPE eq`) produced no index candidate and is cited by no rationale row; the ETL extract `ap-fa4086177d` likewise. The unenforced-pointer index candidates (`INVOICE_ID`, `CUST_ID`, `TENANT_ID`) are listed in `modeling.dropped_indexes` only where they were a left prefix of a planned index — none here, so they simply do not appear.
- **Package evidence:** none; both tables are reached only from `app/reports.py` and `etl/legacy-extra/tools/oracle_custbill_extract.py`.
- **Agreement / contradiction with `03_access_review.md`:** check 4 established that the one read touching both tables is batch-scoped (`h.batch_no = :batch_no`, join `h.invoice_id = l.invoice_id`, no equality on `INVOICE_LINE.INVOICE_ID` to a parameter) and therefore *not* per-parent evidence; the proposer's `reference` agrees. §3.17 keeps `INVOICE_LINE` (CUSTBILL, no FK) apart from the transactional `INVOICE_LINES` (FK `FK_IL_INVOICE`), and so does the spec: `INVOICES → INVOICE_LINES` is `read_by_parent_key` / `embed` / `derived` (array `lines`), `INVOICE_HEADER → INVOICE_LINE` is a reference. One thing to carry forward, not a contradiction: `pointer_unresolved` shows 37 of 1500 `INVOICE_LINE.INVOICE_ID` values do not resolve to `INVOICE_HEADER`, and `target_alternatives` names `INVOICES`; the review did not measure this.

### 2.3 `ENTITY_ATTR_VALUE` → `entityAttrValue`

- **Shape:** own collection. `decision.shape` = `collection`, `key` `{"source": ["EAV_ID"], "target": "_id"}`, `key_strategy` = `sequence+trigger identity: keep numeric _id on load, application generates ids after cutover`, `key_strategy_evidence` `{"origin": "ddl_census", "evidence": "trigger TRG_ENTITY_ATTR_VALUE_SEQ assigns NEXTVAL"}`, `pattern` = `eav`, `proposal` = "attribute pattern: array of {k, v, type} under the owning entity once ownership is known; separate collection until then", `eav_measurements` `{"distinct_attrs": 8, "p99_attrs_per_entity": 1, "max_attrs_per_entity": 1, "entities": 70}`.
- **Rule fired:** none. `ENTITY_ATTR_VALUE` appears in **no** `modeling.rationale` row — the `(ENTITY_TYPE, ENTITY_ID)` pair is a `polymorphic_pointer` trap, not an `unenforced_pointer`, so not even a `pointer_only_no_fk` row was emitted. The collection decision comes from the census `eav` trap:

```json
[
  {
    "pattern": "eav",
    "detail": "attribute pattern: array of {k, v, type} under the owning entity once ownership is known; separate collection until then",
    "evidence": "proposed from census trap"
  }
]
```

- **`open_questions` by kind:**

- **`polymorphic_pointer`**

```json
{
  "kind": "polymorphic_pointer",
  "table": "ENTITY_ATTR_VALUE",
  "evidence": [
    {
      "kind": "ddl",
      "ref": "ENTITY_TYPE identifies the target type for ENTITY_ID"
    },
    {
      "kind": "data_profile",
      "ref": "value_domain:ENTITY_ATTR_VALUE.ENTITY_TYPE"
    }
  ],
  "columns": [
    "ENTITY_TYPE",
    "ENTITY_ID"
  ],
  "proposal": "polymorphic reference (ENTITY_TYPE, ENTITY_ID): store as {coll: <type>, id: <id>} or one optional ref field per type; it cannot be embedded or FK-joined; confirm the type domain",
  "observed_types": [
    "CUSTOMER"
  ]
}
```

- **`date_as_string`**

```json
{
  "kind": "date_as_string",
  "table": "ENTITY_ATTR_VALUE",
  "evidence": "date kept as text",
  "columns": [
    "CREATED_DT"
  ]
}
```

- **`single_valued_index_key`**

```json
{
  "kind": "single_valued_index_key",
  "table": "ENTITY_ATTR_VALUE",
  "column": "ENTITY_TYPE",
  "distinct_values": 1,
  "evidence": [
    {
      "kind": "data_profile",
      "ref": "value_domain:ENTITY_ATTR_VALUE.ENTITY_TYPE"
    }
  ],
  "proposal": "profile shows one non-null value; confirm the domain on the real estate before relying on this access-index plan"
}
```

- **Index candidates:**

```json
[
  {
    "keys": [
      [
        "entityId",
        1
      ],
      [
        "_id",
        1
      ]
    ],
    "origin": "access",
    "evidence": [
      {
        "kind": "access_pattern",
        "ref": "ap-6c1786cb2d"
      }
    ]
  }
]
```

  `entityType` is omitted from the key because of the `single_valued_index_key` question above (one observed value, `CUSTOMER`).
- **Package evidence:** none (check 5: "No package reads it"). The index evidence `ap-6c1786cb2d` is `app/facade.py:294-296`.
- **Contradiction with `03_access_review.md`:** check 5 established the owner — `GET /customer` reads `CUSTOMER_MASTER` by tenant (`ap-e45fe9768e`) and then `ENTITY_ATTR_VALUE WHERE entity_type = 'CUSTOMER' AND entity_id = :1` with `:1 = cust_id` (`ap-6c1786cb2d`); it is "never read alone and never joined". The proposer says "separate collection until [ownership] is known" and reports `observed_types: ["CUSTOMER"]`, but did not turn the two-statement read into a `CUSTOMER_MASTER → ENTITY_ATTR_VALUE` edge or rationale row (no census relationship, as §3.5 predicted). The evidence for ownership exists in the confirmed set; the spec does not use it. Not fixed here.

### 2.4 `CODES` → `codes` (and every `*_CD` column)

- **Shape:** own collection. `decision.shape` = `collection`, `key` `{"source": ["CODE_TYPE", "CODE_VAL"], "target": ["codeType", "codeVal"]}`, `key_strategy` = `natural primary key`, `pattern` = `reference_data`, `patterns` `[{"pattern": "reference_data", "detail": "reference_data", "evidence": "proposed from census trap", "origin": "ddl_census"}]`.
- **Rule fired:** none — `CODES` is in no rationale row (no FK or pointer names it; `*_CD` columns are `code_lookup` traps, not pointers). No `lookup_reference` row exists for any `*_CD` → `CODES` pair; the only `lookup_reference` in the spec is `TENANTS → DUNNING_ATTEMPTS`.
- **`open_questions`:** `decision.open_questions` for `CODES` is `[]` — the proposer raised no question.
- **Index candidates:**

```json
[
  {
    "keys": [
      [
        "codeDesc",
        1
      ],
      [
        "codeType",
        1
      ]
    ],
    "origin": "access",
    "evidence": [
      {
        "kind": "access_pattern",
        "ref": "ap-6470faec0f"
      }
    ]
  },
  {
    "keys": [
      [
        "codeType",
        1
      ],
      [
        "codeVal",
        1
      ]
    ],
    "origin": "access",
    "evidence": [
      {
        "kind": "access_pattern",
        "ref": "ap-0a1051eac3"
      },
      {
        "kind": "access_pattern",
        "ref": "ap-15404b0226"
      },
      {
        "kind": "access_pattern",
        "ref": "ap-3fbad6ec1e"
      },
      {
        "kind": "access_pattern",
        "ref": "ap-88f22eaf5b"
      },
      {
        "kind": "access_pattern",
        "ref": "ap-d9d4207c37"
      },
      {
        "kind": "access_pattern",
        "ref": "ap-fe087c4e0c"
      }
    ]
  }
]
```

  Evidence routines: `ap-6470faec0f` → `services/legacy-billing/app/facade.py`; `ap-0a1051eac3` → `services/legacy-billing/app/facade.py`; `ap-15404b0226` → `services/legacy-billing/app/facade.py`; `ap-3fbad6ec1e` → `services/legacy-billing/app/facade.py`; `ap-88f22eaf5b` → `services/legacy-billing/app/facade.py`; `ap-d9d4207c37` → `pkg_ow_util.f_code_desc`; `ap-fe087c4e0c` → `trg_usage_events_check`. `modeling.dropped_indexes` drops the DDL index on `CODES(CODE_TYPE)` as "left prefix of planned index".
- **Package evidence:** one package pattern cites `CODES` — `ap-d9d4207c37` (`pkg_ow_util.f_code_desc`, `01_pkg_util.sql:40`) — and it is **not** cited by any index or rationale row; the index evidence is app (`facade.py`) and trigger (`trg_usage_events_check`, `ap-fe087c4e0c`) reads.

**Every `*_CD` column** (census), with the proposer's `code_lookup` question and the access-review finding (check 6):

| table | column | type | `code_lookup` question | proposer `proposal` (quoted, trimmed) | `03_access_review.md` check 6 |
|---|---|---|---|---|---|
| `CUSTOMER_MASTER` | `STATE_CD` | `VARCHAR2` | **no** |  | never joined to CODES anywhere (`CUST_STATUS`/`CUST_TYPE`/`PHONE_TYPE` seeded at `02_horror.sql:9-19` but unused) |
| `CUSTOMER_MASTER` | `COUNTRY_CD` | `VARCHAR2` | **no** |  | never joined to CODES anywhere (`CUST_STATUS`/`CUST_TYPE`/`PHONE_TYPE` seeded at `02_horror.sql:9-19` but unused) |
| `CUSTOMER_MASTER` | `MAIL_STATE_CD` | `VARCHAR2` | **no** |  | never joined to CODES anywhere (`CUST_STATUS`/`CUST_TYPE`/`PHONE_TYPE` seeded at `02_horror.sql:9-19` but unused) |
| `CUSTOMER_MASTER` | `PHONE1_TYPE_CD` | `NUMBER` | yes | ambiguous: PHONE1_TYPE_CD: CUST_STATUS, CUST_TYPE, NOTIF_KIND, PHONE_TYPE, PLAN_TIER, USAGE_KIND all cover the domain | never joined to CODES anywhere (`CUST_STATUS`/`CUST_TYPE`/`PHONE_TYPE` seeded at `02_horror.sql:9-19` but unused) |
| `CUSTOMER_MASTER` | `PHONE2_TYPE_CD` | `NUMBER` | yes | PHONE2_TYPE_CD: CUST_STATUS, CUST_TYPE, NOTIF_KIND, PHONE_TYPE, PLAN_TIER, USAGE_KIND all cover the domain | never joined to CODES anywhere (`CUST_STATUS`/`CUST_TYPE`/`PHONE_TYPE` seeded at `02_horror.sql:9-19` but unused) |
| `CUSTOMER_MASTER` | `PHONE3_TYPE_CD` | `NUMBER` | yes | keep the numeric code and denormalize the label from the codes table: STATUS_CD -> CUST_STATUS. ambiguous: PHONE1_TYPE_CD: CUST_STATUS, CUST_TYPE, NOTIF_KIND, P | never joined to CODES anywhere (`CUST_STATUS`/`CUST_TYPE`/`PHONE_TYPE` seeded at `02_horror.sql:9-19` but unused) |
| `CUSTOMER_MASTER` | `PHONE4_TYPE_CD` | `NUMBER` | yes | keep the numeric code and denormalize the label from the codes table: STATUS_CD -> CUST_STATUS. ambiguous: PHONE1_TYPE_CD: CUST_STATUS, CUST_TYPE, NOTIF_KIND, P | never joined to CODES anywhere (`CUST_STATUS`/`CUST_TYPE`/`PHONE_TYPE` seeded at `02_horror.sql:9-19` but unused) |
| `CUSTOMER_MASTER` | `STATUS_CD` | `NUMBER` | yes | keep the numeric code and denormalize the label from the codes table: STATUS_CD -> CUST_STATUS | never joined to CODES anywhere (`CUST_STATUS`/`CUST_TYPE`/`PHONE_TYPE` seeded at `02_horror.sql:9-19` but unused) |
| `CUSTOMER_MASTER` | `SUB_STATUS_CD` | `NUMBER` | yes | SUB_STATUS_CD: CUST_STATUS, CUST_TYPE, NOTIF_KIND, PHONE_TYPE, PLAN_TIER, USAGE_KIND all cover the domain | never joined to CODES anywhere (`CUST_STATUS`/`CUST_TYPE`/`PHONE_TYPE` seeded at `02_horror.sql:9-19` but unused) |
| `CUSTOMER_MASTER` | `CUST_TYPE_CD` | `NUMBER` | yes | CUST_TYPE_CD: CUST_STATUS, CUST_TYPE, NOTIF_KIND, PHONE_TYPE, PLAN_TIER, USAGE_KIND all cover the domain | never joined to CODES anywhere (`CUST_STATUS`/`CUST_TYPE`/`PHONE_TYPE` seeded at `02_horror.sql:9-19` but unused) |
| `CUSTOMER_MASTER` | `SEGMENT_CD` | `NUMBER` | yes | SEGMENT_CD: no single code type covers every value (PHONE_TYPE, CUST_STATUS, CUST_TYPE, NOTIF_KIND) | never joined to CODES anywhere (`CUST_STATUS`/`CUST_TYPE`/`PHONE_TYPE` seeded at `02_horror.sql:9-19` but unused) |
| `CUSTOMER_MASTER` | `REGION_CD` | `NUMBER` | yes | REGION_CD: no single code type covers every value (PHONE_TYPE, CUST_STATUS, CUST_TYPE, NOTIF_KIND). unresolved: SEGMENT_CD: 5 value(s) in 101 row(s) match no co | never joined to CODES anywhere (`CUST_STATUS`/`CUST_TYPE`/`PHONE_TYPE` seeded at `02_horror.sql:9-19` but unused) |
| `CUSTOMER_MASTER` | `TERRITORY_CD` | `NUMBER` | yes | keep the numeric code and denormalize the label from the codes table: STATUS_CD -> CUST_STATUS. ambiguous: PHONE1_TYPE_CD: CUST_STATUS, CUST_TYPE, NOTIF_KIND, P | never joined to CODES anywhere (`CUST_STATUS`/`CUST_TYPE`/`PHONE_TYPE` seeded at `02_horror.sql:9-19` but unused) |
| `CUSTOMER_MASTER` | `CHANNEL_CD` | `NUMBER` | yes | keep the numeric code and denormalize the label from the codes table: STATUS_CD -> CUST_STATUS. ambiguous: PHONE1_TYPE_CD: CUST_STATUS, CUST_TYPE, NOTIF_KIND, P | never joined to CODES anywhere (`CUST_STATUS`/`CUST_TYPE`/`PHONE_TYPE` seeded at `02_horror.sql:9-19` but unused) |
| `CUSTOMER_MASTER` | `RATE_CLASS_CD` | `NUMBER` | yes | keep the numeric code and denormalize the label from the codes table: STATUS_CD -> CUST_STATUS. ambiguous: PHONE1_TYPE_CD: CUST_STATUS, CUST_TYPE, NOTIF_KIND, P | never joined to CODES anywhere (`CUST_STATUS`/`CUST_TYPE`/`PHONE_TYPE` seeded at `02_horror.sql:9-19` but unused) |
| `CUSTOMER_MASTER_HIST` | `STATE_CD` | `VARCHAR2` | **no** |  | copy of CUSTOMER_MASTER; never joined |
| `CUSTOMER_MASTER_HIST` | `COUNTRY_CD` | `VARCHAR2` | **no** |  | copy of CUSTOMER_MASTER; never joined |
| `CUSTOMER_MASTER_HIST` | `MAIL_STATE_CD` | `VARCHAR2` | **no** |  | copy of CUSTOMER_MASTER; never joined |
| `CUSTOMER_MASTER_HIST` | `PHONE1_TYPE_CD` | `NUMBER` | yes | keep the numeric code; resolve to a label in the app or a codes collection | copy of CUSTOMER_MASTER; never joined |
| `CUSTOMER_MASTER_HIST` | `PHONE2_TYPE_CD` | `NUMBER` | yes | keep the numeric code; resolve to a label in the app or a codes collection | copy of CUSTOMER_MASTER; never joined |
| `CUSTOMER_MASTER_HIST` | `PHONE3_TYPE_CD` | `NUMBER` | yes | keep the numeric code; resolve to a label in the app or a codes collection | copy of CUSTOMER_MASTER; never joined |
| `CUSTOMER_MASTER_HIST` | `PHONE4_TYPE_CD` | `NUMBER` | yes | keep the numeric code; resolve to a label in the app or a codes collection | copy of CUSTOMER_MASTER; never joined |
| `CUSTOMER_MASTER_HIST` | `STATUS_CD` | `NUMBER` | yes | keep the numeric code; resolve to a label in the app or a codes collection | copy of CUSTOMER_MASTER; never joined |
| `CUSTOMER_MASTER_HIST` | `SUB_STATUS_CD` | `NUMBER` | yes | keep the numeric code; resolve to a label in the app or a codes collection | copy of CUSTOMER_MASTER; never joined |
| `CUSTOMER_MASTER_HIST` | `CUST_TYPE_CD` | `NUMBER` | yes | keep the numeric code; resolve to a label in the app or a codes collection | copy of CUSTOMER_MASTER; never joined |
| `CUSTOMER_MASTER_HIST` | `SEGMENT_CD` | `NUMBER` | yes | keep the numeric code; resolve to a label in the app or a codes collection | copy of CUSTOMER_MASTER; never joined |
| `CUSTOMER_MASTER_HIST` | `REGION_CD` | `NUMBER` | yes | keep the numeric code; resolve to a label in the app or a codes collection | copy of CUSTOMER_MASTER; never joined |
| `CUSTOMER_MASTER_HIST` | `TERRITORY_CD` | `NUMBER` | yes | keep the numeric code; resolve to a label in the app or a codes collection | copy of CUSTOMER_MASTER; never joined |
| `CUSTOMER_MASTER_HIST` | `CHANNEL_CD` | `NUMBER` | yes | keep the numeric code; resolve to a label in the app or a codes collection | copy of CUSTOMER_MASTER; never joined |
| `CUSTOMER_MASTER_HIST` | `RATE_CLASS_CD` | `NUMBER` | yes | keep the numeric code; resolve to a label in the app or a codes collection | copy of CUSTOMER_MASTER; never joined |
| `DUNNING_ATTEMPTS` | `STATUS_CD` | `NUMBER` | **no** |  | app join → `DUN_STATUS` (`facade.py:342-344`) |
| `INVOICES` | `STATUS_CD` | `NUMBER` | yes | keep the numeric code and denormalize the label from the codes table: STATUS_CD -> INV_STATUS | app join → `INV_STATUS` (`facade.py:245-247`) |
| `INVOICE_HEADER` | `STATUS_CD` | `NUMBER` | yes | keep the numeric code and denormalize the label from the codes table: STATUS_CD -> INV_STATUS | app join → `INV_STATUS` (`reports.py:49-50`, `:72-73`) |
| `INVOICE_LINE` | `LINE_TYPE_CD` | `NUMBER` | yes | ambiguous: LINE_TYPE_CD: no single code type covers every value (CUST_STATUS, CUST_TYPE, NOTIF_KIND, PHONE_TYPE). unresolved: LINE_TYPE_CD: 1 value(s) in 256 ro | never joined; `DECODE` in `reports.py:57-61`, `:75-79` |
| `NOTIFICATIONS` | `KIND_CD` | `NUMBER` | yes | ambiguous: KIND_CD: CUST_STATUS, CUST_TYPE, NOTIF_KIND, PHONE_TYPE, PLAN_TIER, USAGE_KIND all cover the domain | never joined |
| `PLANS` | `TIER_CD` | `NUMBER` | yes | ambiguous: TIER_CD: CUST_STATUS, CUST_TYPE, NOTIF_KIND, PHONE_TYPE, PLAN_TIER, USAGE_KIND all cover the domain | never joined; package `DECODE` (`02_pkg_plans.sql:26-27`, `:55-56`) |
| `SUBSCRIPTIONS` | `STATUS_CD` | `NUMBER` | yes | ambiguous: STATUS_CD: DUN_STATUS, INV_STATUS, SUB_STATUS, TENANT_STATUS all cover the domain | never joined; package `DECODE` (`02_pkg_plans.sql:58-59`, `:93`) |
| `SUBSCRIPTIONS_HIST` | `STATUS_CD` | `NUMBER` | yes | ambiguous: STATUS_CD: DUN_STATUS, INV_STATUS, SUB_STATUS, TENANT_STATUS all cover the domain | never joined (copy of SUBSCRIPTIONS) |
| `TENANTS` | `STATUS_CD` | `NUMBER` | yes | ambiguous: STATUS_CD: DUN_STATUS, INV_STATUS, SUB_STATUS, TENANT_STATUS all cover the domain | app join → `TENANT_STATUS` (`facade.py:114-116`); package `DECODE` (`05_pkg_dunning.sql:23-24`) |
| `USAGE_EVENTS` | `KIND_CD` | `NUMBER` | yes | ambiguous: KIND_CD: CUST_STATUS, CUST_TYPE, NOTIF_KIND, PHONE_TYPE, PLAN_TIER, USAGE_KIND all cover the domain | trigger + app join → `USAGE_KIND` (`01_tables.sql:248-249`, `facade.py:215-217`, `:394-396`); package `DECODE` (`03_pkg_rating.sql:147-148`, `:156-157`) |

Observations (recorded, not fixed):

- The census `code_lookup` trap is "`*_CD` numeric columns", so the three `VARCHAR2` codes `STATE_CD`, `COUNTRY_CD`, `MAIL_STATE_CD` (and their `CUSTOMER_MASTER_HIST` copies) carry no question and stay plain strings.
- `DUNNING_ATTEMPTS.STATUS_CD` has **no** `code_lookup` question even though it is one of the five columns the app actually joins to `CODES` (`ap-0a1051eac3` → `DUN_STATUS`); it is embedded under `INVOICES` and the trap did not follow it.
- Every "denormalize the label … `STATUS_CD -> CUST_STATUS`" / "ambiguous: … all cover the domain" proposal rests on `value_domain`/`code_resolve` overlap in the data profile, not on an application join. Check 6 says the packages resolve codes with inline `DECODE` literals and never join `CODES`, and that *every* `CUSTOMER_MASTER.*_CD` is never joined anywhere. The proposer's `STATUS_CD -> CUST_STATUS` for `CUSTOMER_MASTER` therefore has no application evidence behind it — contradiction to carry into `05_decisions.md`.

### 2.5 Packed / CSV and dirty-date columns of `CUSTOMER_MASTER`

- **Shape:** all stay scalar fields of `customerMaster` — the proposer did not fold any numbered series into an array. The `repeating_group` question (quoted in §2.1) lists the candidate arrays: `ADDR_LINE_1..6`, `MAIL_ADDR_LINE_1..6`, `PHONE1..4`, `EMAIL_1..3`, `FLAG_01..20`, `UDF_01..20`. Generated field rows for the first member of each series:

```json
[
  {
    "source": "ADDR_LINE_1",
    "target": "addrLine1",
    "source_type": "VARCHAR2(120)",
    "bson_type": "string",
    "rules": [
      "empty_string_is_null",
      "null_missing_equiv"
    ]
  },
  {
    "source": "MAIL_ADDR_LINE_1",
    "target": "mailAddrLine1",
    "source_type": "VARCHAR2(120)",
    "bson_type": "string",
    "rules": [
      "empty_string_is_null",
      "null_missing_equiv"
    ]
  },
  {
    "source": "PHONE1",
    "target": "phone1",
    "source_type": "VARCHAR2(25)",
    "bson_type": "string",
    "rules": [
      "empty_string_is_null",
      "null_missing_equiv"
    ]
  },
  {
    "source": "EMAIL_1",
    "target": "email1",
    "source_type": "VARCHAR2(200)",
    "bson_type": "string",
    "rules": [
      "empty_string_is_null",
      "null_missing_equiv"
    ]
  },
  {
    "source": "FLAG_01",
    "target": "flag01",
    "source_type": "CHAR(1)",
    "bson_type": "string",
    "rules": [
      "rstrip_spaces",
      "empty_string_is_null",
      "null_missing_equiv"
    ]
  },
  {
    "source": "UDF_01",
    "target": "udf01",
    "source_type": "VARCHAR2(100)",
    "bson_type": "string",
    "rules": [
      "empty_string_is_null",
      "null_missing_equiv"
    ]
  }
]
```

- **CSV columns** become arrays via `csv_to_array`; the `csv_list` question (§2.1) carries the measurements (`RELATED_ACCT_IDS` max 4 / avg 2.59; `CHILD_ACCT_IDS` unmeasured; `PROMO_CODES_CSV` max 2 / avg 1.48):

```json
[
  {
    "source": "RELATED_ACCT_IDS",
    "target": "relatedAcctIds",
    "source_type": "VARCHAR2(2000)",
    "bson_type": "array",
    "rules": [
      "csv_to_array",
      "null_missing_equiv"
    ]
  },
  {
    "source": "CHILD_ACCT_IDS",
    "target": "childAcctIds",
    "source_type": "VARCHAR2(2000)",
    "bson_type": "array",
    "rules": [
      "csv_to_array",
      "null_missing_equiv"
    ]
  },
  {
    "source": "PROMO_CODES_CSV",
    "target": "promoCodes",
    "source_type": "VARCHAR2(1000)",
    "bson_type": "array",
    "rules": [
      "csv_to_array",
      "null_missing_equiv"
    ]
  }
]
```

- **Dirty-date columns** (`VARCHAR2(9)` → `bson_type: date`): two carry a measured format, three carry `date_string_to_date` with **no** format and are listed in `modeling.unresolved` as `date_format_assumed … unmeasurable in this profile` (§4):

```json
[
  {
    "source": "SIGNUP_DT",
    "target": "signupDt",
    "source_type": "VARCHAR2(9)",
    "bson_type": "date",
    "rules": [
      "date_string_to_date:dby-b3d57e",
      "null_missing_equiv"
    ],
    "date_format": "%d-%b-%y",
    "date_format_basis": "data_profile"
  },
  {
    "source": "LAST_ACTIVITY_DT",
    "target": "lastActivityDt",
    "source_type": "VARCHAR2(9)",
    "bson_type": "date",
    "rules": [
      "date_string_to_date:dby-b3d57e",
      "null_missing_equiv"
    ],
    "date_format": "%d-%b-%y",
    "date_format_basis": "data_profile"
  },
  {
    "source": "LAST_INVOICE_DT",
    "target": "lastInvoiceDt",
    "source_type": "VARCHAR2(9)",
    "bson_type": "date",
    "rules": [
      "date_string_to_date",
      "null_missing_equiv"
    ]
  },
  {
    "source": "LAST_PAYMENT_DT",
    "target": "lastPaymentDt",
    "source_type": "VARCHAR2(9)",
    "bson_type": "date",
    "rules": [
      "date_string_to_date",
      "null_missing_equiv"
    ]
  },
  {
    "source": "TERMINATE_DT",
    "target": "terminateDt",
    "source_type": "VARCHAR2(9)",
    "bson_type": "date",
    "rules": [
      "date_string_to_date",
      "null_missing_equiv"
    ]
  }
]
```

  - `SIGNUP_DT`: `date_format_nonconforming`, `measured_format %d-%b-%y`, `conformance 0.845771`, `est_bad_rows 32` of 201 — the profile's shapes include `99-XXX-99`, `N/A`, `  -   -  `, `99-99-999`, `9/9/9999`. The proposer's `proposal` is "quarantine approximately 32 rows … confirm the bad-row handling policy".
  - `LAST_ACTIVITY_DT`: `%d-%b-%y` at `conformance 1.0` — recorded in `modeling.answered` as `date_format_assumed`, i.e. measured and closed.
  - `LAST_INVOICE_DT`, `LAST_PAYMENT_DT`, `TERMINATE_DT`: `text_shapes` returned `shapes: []` (no non-null values in the profile), so the format is an assumption the proposer flags, not a measurement.
- **Index / package evidence:** none specific to these columns.
- **Contradiction with `03_access_review.md`:** none; the review has no access evidence for these columns (CUSTBILL estate is read only by the batch report and the ETL extract).

### 2.6 `SUBSCRIPTIONS_HIST` → `subscriptionsHist`

- **Shape:** own collection. `decision.shape` = `collection`, `key` `{"source": ["HIST_ID"], "target": "_id"}`, `key_strategy` = `natural primary key`, `pattern` = `history_copy`, `of_table` = `SUBSCRIPTIONS`, `proposal` = "separate versions collection keyed by history id; do not embed unbounded history", `patterns` `[{"pattern": "history_copy", "detail": "separate versions collection keyed by history id; do not embed unbounded history", "evidence": "proposed from census trap"}]`. Not embedded under `SUBSCRIPTIONS`.
- **Rules fired:** `TENANTS → SUBSCRIPTIONS_HIST` and `PLANS → SUBSCRIPTIONS_HIST` = `pointer_only_no_fk` / `reference` / `assumed`. **There is no `SUBSCRIPTIONS → SUBSCRIPTIONS_HIST` row at all.** Cause, read from the inputs: the base-row key column in `SUBSCRIPTIONS_HIST` is named `ID` (census columns `["HIST_ID", "HIST_DT", "HIST_OP", "ID", "TENANT_ID", "PLAN_ID", "STARTS_ON", "ENDS_ON", "STATUS_CD", "SUSPENDED_ON"]`, `foreign_keys` `[]`), so the census `unenforced_pointer` trap ("`*_ID` column with a matching table and no FK") does not bind it to `SUBSCRIPTIONS`; without a census relationship or pointer the proposer never evaluates the pair, and `rule_written_together` (`model_relationships.py`) is only reached per evaluated edge.
- **`written_together` with `via_trigger`:** **does not appear** — neither string occurs anywhere in `mapping_spec.json`. The confirmed, pinned evidence it would have cited is in `access_patterns.json`: `ap-a7af1a6156` (`pkg_plans.sp_change_plan` UPDATE, `cascades: ["ap-bdfdef0db0"]`), `ap-d3754b6b8a` (`pkg_dunning.sp_suspend_overdue`), `ap-f95317f034` (`app/backends/oracle.py` UPDATE) → `ap-bdfdef0db0` (`trg_subscriptions_hist`, `trigger: {on: SUBSCRIPTIONS, events: [update, delete]}`). `ap-a7af1a6156` *is* cited — but only in the `PLANS → SUBSCRIPTIONS` and `TENANTS → SUBSCRIPTIONS` `shared_child` rows.
- **`rationale` rows (quoted):**

```json
{
  "parent": "TENANTS",
  "child": "SUBSCRIPTIONS_HIST",
  "child_columns": [
    "TENANT_ID"
  ],
  "rule": "pointer_only_no_fk",
  "decision": "reference",
  "basis": "assumed",
  "basis_sources": [
    "ddl"
  ],
  "evidence": [
    {
      "kind": "ddl",
      "ref": "*_ID column with a matching table and no FK"
    }
  ]
}
```
```json
{
  "parent": "PLANS",
  "child": "SUBSCRIPTIONS_HIST",
  "child_columns": [
    "PLAN_ID"
  ],
  "rule": "pointer_only_no_fk",
  "decision": "reference",
  "basis": "assumed",
  "basis_sources": [
    "ddl"
  ],
  "evidence": [
    {
      "kind": "ddl",
      "ref": "*_ID column with a matching table and no FK"
    }
  ]
}
```

- **`open_questions` by kind:**

- **`date_format_nonconforming`**

```json
{
  "kind": "date_format_nonconforming",
  "table": "SUBSCRIPTIONS_HIST",
  "column": "HIST_DT",
  "measured_format": "%Y%m%d",
  "conformance": 0.0,
  "rows_shaped": 6,
  "est_bad_rows": 6,
  "evidence": {
    "kind": "data_profile",
    "ref": "text_shapes:SUBSCRIPTIONS_HIST.HIST_DT"
  },
  "proposal": "quarantine approximately 6 rows that do not match '%Y%m%d' before converting SUBSCRIPTIONS_HIST.HIST_DT; confirm the bad-row handling policy"
}
```

- **`unenforced_pointer`**

```json
{
  "kind": "unenforced_pointer",
  "table": "SUBSCRIPTIONS_HIST",
  "evidence": [
    {
      "kind": "ddl",
      "ref": "*_ID column with a matching table and no FK"
    },
    {
      "kind": "data_profile",
      "ref": "pointer_resolve:SUBSCRIPTIONS_HIST.TENANT_ID->TENANTS"
    },
    {
      "kind": "data_profile",
      "ref": "pointer_resolve:SUBSCRIPTIONS_HIST.PLAN_ID->PLANS"
    }
  ],
  "columns": [
    "TENANT_ID",
    "PLAN_ID"
  ],
  "targets": [
    "TENANTS",
    "PLANS"
  ],
  "target_basis": [
    "table_name",
    "table_name"
  ],
  "proposal": "all profiled values resolve: model as a reference and enforce it in the application",
  "measured": {
    "resolve_rate": 1.0
  }
}
```

- **`code_lookup`**

```json
{
  "kind": "code_lookup",
  "table": "SUBSCRIPTIONS_HIST",
  "evidence": [
    {
      "kind": "data_profile",
      "ref": "value_domain:SUBSCRIPTIONS_HIST.STATUS_CD"
    },
    {
      "kind": "data_profile",
      "ref": "code_resolve:SUBSCRIPTIONS_HIST.STATUS_CD"
    }
  ],
  "columns": [
    "STATUS_CD"
  ],
  "proposal": "ambiguous: STATUS_CD: DUN_STATUS, INV_STATUS, SUB_STATUS, TENANT_STATUS all cover the domain; the app or a type column must say which",
  "measurements": {
    "STATUS_CD": {
      "distinct_values": 1,
      "null_count": 0,
      "code_resolution": {
        "distinct_values": 1,
        "candidates": [
          {
            "code_type": "DUN_STATUS",
            "distinct_values": 1,
            "rows": 6
          },
          {
            "code_type": "INV_STATUS",
            "distinct_values": 1,
            "rows": 6
          },
          {
            "code_type": "SUB_STATUS",
            "distinct_values": 1,
            "rows": 6
          },
          {
            "code_type": "TENANT_STATUS",
            "distinct_values": 1,
            "rows": 6
          }
        ],
        "full_cover": [
          "DUN_STATUS",
          "INV_STATUS",
          "SUB_STATUS",
          "TENANT_STATUS"
        ],
        "unresolved_distinct": 0,
        "unresolved_rows": 0,
        "unresolved_values": []
      }
    }
  }
}
```

- **`date_as_string`**

```json
{
  "kind": "date_as_string",
  "table": "SUBSCRIPTIONS_HIST",
  "evidence": "date kept as text",
  "columns": [
    "HIST_DT"
  ]
}
```

- **Index candidates:** `indexes` for `subscriptionsHist` is `[]` — no index candidate.
- **Package evidence:** none cited for this table. `TRG_SUBSCRIPTIONS_HIST` is listed in `modeling.unresolved` as `trigger_business_logic` (§4).
- **Contradictions with `03_access_review.md`:**
  1. §3 consequences: "SUBSCRIPTIONS → SUBSCRIPTIONS_HIST: `written_together` via trigger from three confirmed UPDATEs (check 1)". The spec has no such row and no `via_trigger` — the proposer did not consume the pinned cascade evidence because the edge was never constructed (see cause above). Not fixed here.
  2. `HIST_DT`: the field row is `{"rules": ["date_string_to_date:Ymd-0e0ea1", …], "date_format": "%Y%m%d", "date_format_basis": "data_profile"}` while the `date_format_nonconforming` question on the same column reports `measured_format %Y%m%d`, `conformance 0.0`, `est_bad_rows 6` of 6 — the profile's single shape is `99-OCT-99 99:99:99` (a `%d-%b-%y %H:%M:%S` shape that is not in the profiler's candidate list). The spec thus pins a format that matches zero rows. Internal inconsistency of the proposer output, not an access-review contradiction; recorded for `05_decisions.md`.

### 2.7 `BILLING_AUDIT_LOG` → `billingAuditLog`

- **Shape:** own collection. `decision.shape` = `collection`, `key` `{"source": ["LOG_ID"], "target": "_id"}`, `key_strategy` = "sequence+trigger identity: keep numeric _id on load, application generates ids after cutover", `key_strategy_evidence` `{"origin": "ddl_census", "evidence": "trigger TRG_BILLING_AUDIT_LOG_ID assigns NEXTVAL"}`, `embeds` = `[]`, `decision.references` = `[]`. Fields: `["LOGGED_AT", "MODULE", "MESSAGE"]`.
- **Rule fired:** none — the table has no FK and no `*_ID` pointer, so it is in no rationale row. Nothing is embedded under it and it is embedded nowhere.
- **`written_together` / `via_trigger`:** not applicable and absent. The writer `ap-779ce5b5b7` (`pkg_ow_util.log_msg`, `hot`, pinned) and the retention delete `ap-e7b18e81b8` (`job:JOB_PURGE_AUDIT_LOG`, `cold`, pinned) are confirmed but cited by nothing in the spec; the proposer records no `detached`/autonomous marker because the scanner emits none (`03_access_review.md` §3.3).
- **`open_questions`:** `decision.open_questions` for `BILLING_AUDIT_LOG` is `[]` — the proposer raised no question.
- **Index candidates:** `indexes` for `billingAuditLog` is `[]` — no index candidate. (the purge filter `LOGGED_AT range` produced none).
- **Package evidence:** `modeling.application_evidence.files` includes `services/legacy-billing/db/oracle/packages/01_pkg_util.sql` (the only writer) and `schema/04_jobs.sql` (the purge); `TRG_BILLING_AUDIT_LOG_ID` is closed in `modeling.answered` as `sequence_trigger_identity`; `JOB_PURGE_AUDIT_LOG` is in `modeling.unresolved` as `scheduler_job` (§4).
- **Agreement with `03_access_review.md`:** check 3 / §3 consequences "detached writer + retention delete; never embed" — the spec keeps it a separate collection. The *reason* (PRAGMA AUTONOMOUS_TRANSACTION, own COMMIT / ROLLBACK) is not represented in the JSON and must be carried into `05_decisions.md` explicitly, as the review already said.

### 2.8 `CUSTOMER_MASTER_HIST` → `customerMasterHist`

- **Shape:** own collection. `decision.shape` = `collection`, `key` `{"source": ["HIST_ID"], "target": "_id"}`, `key_strategy` = `natural primary key`, `pattern` = `history_copy`, `of_table` = `CUSTOMER_MASTER`, `proposal` = "separate versions collection keyed by history id; do not embed unbounded history", `patterns` `[{"pattern": "history_copy", "detail": "separate versions collection keyed by history id; do not embed unbounded history", "evidence": "proposed from census trap"}]`. Not embedded under `CUSTOMER_MASTER`. `row_estimate` in the census is 0.
- **Rules fired:** `CUSTOMER_MASTER → CUSTOMER_MASTER_HIST` (via `CUST_ID`) and `TENANTS → CUSTOMER_MASTER_HIST` = `pointer_only_no_fk` / `reference` / `assumed`.
- **`written_together` with `via_trigger`:** **does not appear.** The trigger row `ap-dbf1b410e9` (`trg_customer_master_hist`, `cold`, pinned) is cited by nothing in the spec.
- **`rationale` rows (quoted):**

```json
{
  "parent": "CUSTOMER_MASTER",
  "child": "CUSTOMER_MASTER_HIST",
  "child_columns": [
    "CUST_ID"
  ],
  "rule": "pointer_only_no_fk",
  "decision": "reference",
  "basis": "assumed",
  "basis_sources": [
    "ddl"
  ],
  "evidence": [
    {
      "kind": "ddl",
      "ref": "*_ID column with a matching table and no FK"
    }
  ]
}
```
```json
{
  "parent": "TENANTS",
  "child": "CUSTOMER_MASTER_HIST",
  "child_columns": [
    "TENANT_ID"
  ],
  "rule": "pointer_only_no_fk",
  "decision": "reference",
  "basis": "assumed",
  "basis_sources": [
    "ddl"
  ],
  "evidence": [
    {
      "kind": "ddl",
      "ref": "*_ID column with a matching table and no FK"
    }
  ]
}
```

- **`open_questions` by kind** (all `measurements` are `null` — the table is empty in the fixture):

- **`repeating_group`**

```json
{
  "kind": "repeating_group",
  "table": "CUSTOMER_MASTER_HIST",
  "evidence": "numbered column series; candidate arrays",
  "groups": {
    "ADDR_LINE": [
      "ADDR_LINE_1",
      "ADDR_LINE_2",
      "ADDR_LINE_3",
      "ADDR_LINE_4",
      "ADDR_LINE_5",
      "ADDR_LINE_6"
    ],
    "MAIL_ADDR_LINE": [
      "MAIL_ADDR_LINE_1",
      "MAIL_ADDR_LINE_2",
      "MAIL_ADDR_LINE_3",
      "MAIL_ADDR_LINE_4",
      "MAIL_ADDR_LINE_5",
      "MAIL_ADDR_LINE_6"
    ],
    "PHONE": [
      "PHONE1",
      "PHONE2",
      "PHONE3",
      "PHONE4"
    ],
    "EMAIL": [
      "EMAIL_1",
      "EMAIL_2",
      "EMAIL_3"
    ],
    "FLAG": [
      "FLAG_01",
      "FLAG_02",
      "FLAG_03",
      "FLAG_04",
      "FLAG_05",
      "FLAG_06",
      "FLAG_07",
      "FLAG_08",
      "FLAG_09",
      "FLAG_10",
      "FLAG_11",
      "FLAG_12",
      "FLAG_13",
      "FLAG_14",
      "FLAG_15",
      "FLAG_16",
      "FLAG_17",
      "FLAG_18",
      "FLAG_19",
      "FLAG_20"
    ],
    "UDF": [
      "UDF_01",
      "UDF_02",
      "UDF_03",
      "UDF_04",
      "UDF_05",
      "UDF_06",
      "UDF_07",
      "UDF_08",
      "UDF_09",
      "UDF_10",
      "UDF_11",
      "UDF_12",
      "UDF_13",
      "UDF_14",
      "UDF_15",
      "UDF_16",
      "UDF_17",
      "UDF_18",
      "UDF_19",
      "UDF_20",
      "UDF_21",
      "UDF_22",
      "UDF_23",
      "UDF_24",
      "UDF_25",
      "UDF_26",
      "UDF_27",
      "UDF_28",
      "UDF_29",
      "UDF_30",
      "UDF_31",
      "UDF_32",
      "UDF_33",
      "UDF_34",
      "UDF_35",
      "UDF_36",
      "UDF_37",
      "UDF_38",
      "UDF_39",
      "UDF_40"
    ],
    "UDF_AMT": [
      "UDF_AMT_01",
      "UDF_AMT_02",
      "UDF_AMT_03",
      "UDF_AMT_04",
      "UDF_AMT_05",
      "UDF_AMT_06",
      "UDF_AMT_07",
      "UDF_AMT_08",
      "UDF_AMT_09",
      "UDF_AMT_10"
    ],
    "UDF_DT": [
      "UDF_DT_01",
      "UDF_DT_02",
      "UDF_DT_03",
      "UDF_DT_04",
      "UDF_DT_05",
      "UDF_DT_06",
      "UDF_DT_07",
      "UDF_DT_08",
      "UDF_DT_09",
      "UDF_DT_10"
    ]
  },
  "proposal": "collapse each numbered series into one array field; needs app evidence, mapped 1:1 until then"
}
```

- **`unenforced_pointer`**

```json
{
  "kind": "unenforced_pointer",
  "table": "CUSTOMER_MASTER_HIST",
  "evidence": "*_ID column with a matching table and no FK",
  "columns": [
    "CUST_ID",
    "TENANT_ID"
  ],
  "targets": [
    "CUSTOMER_MASTER",
    "TENANTS"
  ],
  "target_basis": [
    "pk_column",
    "table_name"
  ],
  "proposal": "treat as reference; verify pointer resolves before embedding anything"
}
```

- **`code_lookup`**

```json
{
  "kind": "code_lookup",
  "table": "CUSTOMER_MASTER_HIST",
  "evidence": [
    {
      "kind": "data_profile",
      "ref": "value_domain:CUSTOMER_MASTER_HIST.PHONE1_TYPE_CD"
    },
    {
      "kind": "data_profile",
      "ref": "value_domain:CUSTOMER_MASTER_HIST.PHONE2_TYPE_CD"
    },
    {
      "kind": "data_profile",
      "ref": "value_domain:CUSTOMER_MASTER_HIST.PHONE3_TYPE_CD"
    },
    {
      "kind": "data_profile",
      "ref": "value_domain:CUSTOMER_MASTER_HIST.PHONE4_TYPE_CD"
    },
    {
      "kind": "data_profile",
      "ref": "value_domain:CUSTOMER_MASTER_HIST.STATUS_CD"
    },
    {
      "kind": "data_profile",
      "ref": "value_domain:CUSTOMER_MASTER_HIST.SUB_STATUS_CD"
    },
    {
      "kind": "data_profile",
      "ref": "value_domain:CUSTOMER_MASTER_HIST.CUST_TYPE_CD"
    },
    {
      "kind": "data_profile",
      "ref": "value_domain:CUSTOMER_MASTER_HIST.SEGMENT_CD"
    },
    {
      "kind": "data_profile",
      "ref": "value_domain:CUSTOMER_MASTER_HIST.REGION_CD"
    },
    {
      "kind": "data_profile",
      "ref": "value_domain:CUSTOMER_MASTER_HIST.TERRITORY_CD"
    },
    {
      "kind": "data_profile",
      "ref": "value_domain:CUSTOMER_MASTER_HIST.CHANNEL_CD"
    },
    {
      "kind": "data_profile",
      "ref": "value_domain:CUSTOMER_MASTER_HIST.RATE_CLASS_CD"
    },
    {
      "kind": "data_profile",
      "ref": "code_resolve:CUSTOMER_MASTER_HIST.PHONE1_TYPE_CD"
    },
    {
      "kind": "data_profile",
      "ref": "code_resolve:CUSTOMER_MASTER_HIST.PHONE2_TYPE_CD"
    },
    {
      "kind": "data_profile",
      "ref": "code_resolve:CUSTOMER_MASTER_HIST.PHONE3_TYPE_CD"
    },
    {
      "kind": "data_profile",
      "ref": "code_resolve:CUSTOMER_MASTER_HIST.PHONE4_TYPE_CD"
    },
    {
      "kind": "data_profile",
      "ref": "code_resolve:CUSTOMER_MASTER_HIST.STATUS_CD"
    },
    {
      "kind": "data_profile",
      "ref": "code_resolve:CUSTOMER_MASTER_HIST.SUB_STATUS_CD"
    },
    {
      "kind": "data_profile",
      "ref": "code_resolve:CUSTOMER_MASTER_HIST.CUST_TYPE_CD"
    },
    {
      "kind": "data_profile",
      "ref": "code_resolve:CUSTOMER_MASTER_HIST.SEGMENT_CD"
    },
    {
      "kind": "data_profile",
      "ref": "code_resolve:CUSTOMER_MASTER_HIST.REGION_CD"
    },
    {
      "kind": "data_profile",
      "ref": "code_resolve:CUSTOMER_MASTER_HIST.TERRITORY_CD"
    },
    {
      "kind": "data_profile",
      "ref": "code_resolve:CUSTOMER_MASTER_HIST.CHANNEL_CD"
    },
    {
      "kind": "data_profile",
      "ref": "code_resolve:CUSTOMER_MASTER_HIST.RATE_CLASS_CD"
    }
  ],
  "columns": [
    "PHONE1_TYPE_CD",
    "PHONE2_TYPE_CD",
    "PHONE3_TYPE_CD",
    "PHONE4_TYPE_CD",
    "STATUS_CD",
    "SUB_STATUS_CD",
    "CUST_TYPE_CD",
    "SEGMENT_CD",
    "REGION_CD",
    "TERRITORY_CD",
    "CHANNEL_CD",
    "RATE_CLASS_CD"
  ],
  "proposal": "keep the numeric code; resolve to a label in the app or a codes collection",
  "measurements": {
    "PHONE1_TYPE_CD": {
      "distinct_values": 0,
      "null_count": 0,
      "code_resolution": {
        "distinct_values": 0,
        "candidates": [],
        "full_cover": [],
        "unresolved_distinct": 0,
        "unresolved_rows": 0,
        "unresolved_values": []
      }
    },
    "PHONE2_TYPE_CD": {
      "distinct_values": 0,
      "null_count": 0,
      "code_resolution": {
        "distinct_values": 0,
        "candidates": [],
        "full_cover": [],
        "unresolved_distinct": 0,
        "unresolved_rows": 0,
        "unresolved_values": []
      }
    },
    "PHONE3_TYPE_CD": {
      "distinct_values": 0,
      "null_count": 0,
      "code_resolution": {
        "distinct_values": 0,
        "candidates": [],
        "full_cover": [],
        "unresolved_distinct": 0,
        "unresolved_rows": 0,
        "unresolved_values": []
      }
    },
    "PHONE4_TYPE_CD": {
      "distinct_values": 0,
      "null_count": 0,
      "code_resolution": {
        "distinct_values": 0,
        "candidates": [],
        "full_cover": [],
        "unresolved_distinct": 0,
        "unresolved_rows": 0,
        "unresolved_values": []
      }
    },
    "STATUS_CD": {
      "distinct_values": 0,
      "null_count": 0,
      "code_resolution": {
        "distinct_values": 0,
        "candidates": [],
        "full_cover": [],
        "unresolved_distinct": 0,
        "unresolved_rows": 0,
        "unresolved_values": []
      }
    },
    "SUB_STATUS_CD": {
      "distinct_values": 0,
      "null_count": 0,
      "code_resolution": {
        "distinct_values": 0,
        "candidates": [],
        "full_cover": [],
        "unresolved_distinct": 0,
        "unresolved_rows": 0,
        "unresolved_values": []
      }
    },
    "CUST_TYPE_CD": {
      "distinct_values": 0,
      "null_count": 0,
      "code_resolution": {
        "distinct_values": 0,
        "candidates": [],
        "full_cover": [],
        "unresolved_distinct": 0,
        "unresolved_rows": 0,
        "unresolved_values": []
      }
    },
    "SEGMENT_CD": {
      "distinct_values": 0,
      "null_count": 0,
      "code_resolution": {
        "distinct_values": 0,
        "candidates": [],
        "full_cover": [],
        "unresolved_distinct": 0,
        "unresolved_rows": 0,
        "unresolved_values": []
      }
    },
    "REGION_CD": {
      "distinct_values": 0,
      "null_count": 0,
      "code_resolution": {
        "distinct_values": 0,
        "candidates": [],
        "full_cover": [],
        "unresolved_distinct": 0,
        "unresolved_rows": 0,
        "unresolved_values": []
      }
    },
    "TERRITORY_CD": {
      "distinct_values": 0,
      "null_count": 0,
      "code_resolution": {
        "distinct_values": 0,
        "candidates": [],
        "full_cover": [],
        "unresolved_distinct": 0,
        "unresolved_rows": 0,
        "unresolved_values": []
      }
    },
    "CHANNEL_CD": {
      "distinct_values": 0,
      "null_count": 0,
      "code_resolution": {
        "distinct_values": 0,
        "candidates": [],
        "full_cover": [],
        "unresolved_distinct": 0,
        "unresolved_rows": 0,
        "unresolved_values": []
      }
    },
    "RATE_CLASS_CD": {
      "distinct_values": 0,
      "null_count": 0,
      "code_resolution": {
        "distinct_values": 0,
        "candidates": [],
        "full_cover": [],
        "unresolved_distinct": 0,
        "unresolved_rows": 0,
        "unresolved_values": []
      }
    }
  }
}
```

- **`date_as_string`**

```json
{
  "kind": "date_as_string",
  "table": "CUSTOMER_MASTER_HIST",
  "evidence": "date kept as text",
  "columns": [
    "HIST_DT",
    "SIGNUP_DT",
    "LAST_ACTIVITY_DT",
    "LAST_INVOICE_DT",
    "LAST_PAYMENT_DT",
    "TERMINATE_DT"
  ]
}
```

- **`csv_list`**

```json
{
  "kind": "csv_list",
  "table": "CUSTOMER_MASTER_HIST",
  "evidence": [
    {
      "kind": "data_profile",
      "ref": "csv_elements:CUSTOMER_MASTER_HIST.RELATED_ACCT_IDS"
    },
    {
      "kind": "data_profile",
      "ref": "csv_elements:CUSTOMER_MASTER_HIST.CHILD_ACCT_IDS"
    },
    {
      "kind": "data_profile",
      "ref": "csv_elements:CUSTOMER_MASTER_HIST.PROMO_CODES_CSV"
    }
  ],
  "columns": [
    "RELATED_ACCT_IDS",
    "CHILD_ACCT_IDS",
    "PROMO_CODES_CSV"
  ],
  "measurements": {
    "RELATED_ACCT_IDS": {
      "max_elements": null,
      "avg_elements": null
    },
    "CHILD_ACCT_IDS": {
      "max_elements": null,
      "avg_elements": null
    },
    "PROMO_CODES_CSV": {
      "max_elements": null,
      "avg_elements": null
    }
  }
}
```

- **Index candidates:** `indexes` for `customerMasterHist` is `[]` — no index candidate.
- **Package evidence:** none.
- **Contradictions with `03_access_review.md`:**
  1. The review expected (check 2, §3 consequences) "no `written_together`/`via_trigger` evidence for CUSTOMER_MASTER_HIST … expect `default`/`ownership`". Absence of `written_together` agrees; the rule name does not — the proposer stopped at the DDL-only `pointer_only_no_fk` row and never ran the rule order (no census relationship). Same root cause as §2.6.
  2. `modeling.answered` closes **`TRG_CUSTOMER_MASTER_HIST`** as `sequence_trigger_identity` with `evidence: "trigger TRG_CUSTOMER_MASTER_SEQ assigns NEXTVAL"` (§5) — i.e. the history-copy trigger is marked answered on the strength of a *different* trigger's sequence assignment. Check 2 established `trg_customer_master_hist` is AFTER UPDATE OR DELETE inserting the full `:OLD` row. This is a proposer mis-answer; the trigger's business logic is in fact unresolved. Not fixed here.
  3. All six text dates of this table are `date_format_assumed … unmeasurable in this profile` (`rows_shaped 0`) because the table is empty; the review flagged the recon cascade for this table as UNVERIFIED for the same reason.

## 3. History tables — `written_together` / `via_trigger` summary

| history table | `written_together` row | `via_trigger` | evidence the row would have cited (all confirmed + pinned in `access_patterns.json`) | what the spec has instead |
|---|---|---|---|---|
| `SUBSCRIPTIONS_HIST` | absent | absent | `ap-a7af1a6156`, `ap-d3754b6b8a`, `ap-f95317f034` → `cascades: ["ap-bdfdef0db0"]` | `TENANTS →`, `PLANS → SUBSCRIPTIONS_HIST` `pointer_only_no_fk`; `pattern: history_copy` from the census trap |
| `CUSTOMER_MASTER_HIST` | absent (as the review predicted) | absent | none valid — `ap-dbf1b410e9` has no confirmed firing write | `CUSTOMER_MASTER →`, `TENANTS → CUSTOMER_MASTER_HIST` `pointer_only_no_fk`; `pattern: history_copy` |
| `BILLING_AUDIT_LOG` (audit, not a history copy) | n/a — detached writer | n/a | `ap-779ce5b5b7` autonomous | separate collection, no rationale row |

## 4. `modeling.unresolved` — every item

24 items, quoted verbatim in file order:

```json
[
  {
    "kind": "date_format_assumed",
    "table": "CUSTOMER_MASTER_HIST",
    "column": "HIST_DT",
    "format": "%d-%b-%y",
    "note": "unmeasurable in this profile",
    "rows_shaped": 0
  },
  {
    "kind": "date_format_assumed",
    "table": "CUSTOMER_MASTER_HIST",
    "column": "SIGNUP_DT",
    "format": "%d-%b-%y",
    "note": "unmeasurable in this profile",
    "rows_shaped": 0
  },
  {
    "kind": "date_format_assumed",
    "table": "CUSTOMER_MASTER_HIST",
    "column": "LAST_ACTIVITY_DT",
    "format": "%d-%b-%y",
    "note": "unmeasurable in this profile",
    "rows_shaped": 0
  },
  {
    "kind": "date_format_assumed",
    "table": "CUSTOMER_MASTER_HIST",
    "column": "LAST_INVOICE_DT",
    "format": "%d-%b-%y",
    "note": "unmeasurable in this profile",
    "rows_shaped": 0
  },
  {
    "kind": "date_format_assumed",
    "table": "CUSTOMER_MASTER_HIST",
    "column": "LAST_PAYMENT_DT",
    "format": "%d-%b-%y",
    "note": "unmeasurable in this profile",
    "rows_shaped": 0
  },
  {
    "kind": "date_format_assumed",
    "table": "CUSTOMER_MASTER_HIST",
    "column": "TERMINATE_DT",
    "format": "%d-%b-%y",
    "note": "unmeasurable in this profile",
    "rows_shaped": 0
  },
  {
    "kind": "date_format_assumed",
    "table": "CUSTOMER_MASTER",
    "column": "LAST_INVOICE_DT",
    "format": "%d-%b-%y",
    "note": "unmeasurable in this profile",
    "rows_shaped": 0
  },
  {
    "kind": "date_format_assumed",
    "table": "CUSTOMER_MASTER",
    "column": "LAST_PAYMENT_DT",
    "format": "%d-%b-%y",
    "note": "unmeasurable in this profile",
    "rows_shaped": 0
  },
  {
    "kind": "date_format_assumed",
    "table": "CUSTOMER_MASTER",
    "column": "TERMINATE_DT",
    "format": "%d-%b-%y",
    "note": "unmeasurable in this profile",
    "rows_shaped": 0
  },
  {
    "kind": "plsql_unit_needs_manual_review",
    "unit_kind": "PACKAGE",
    "name": "PKG_OW_UTIL"
  },
  {
    "kind": "plsql_unit_needs_manual_review",
    "unit_kind": "PACKAGE BODY",
    "name": "PKG_OW_UTIL"
  },
  {
    "kind": "plsql_unit_needs_manual_review",
    "unit_kind": "PACKAGE",
    "name": "PKG_PLANS"
  },
  {
    "kind": "plsql_unit_needs_manual_review",
    "unit_kind": "PACKAGE BODY",
    "name": "PKG_PLANS"
  },
  {
    "kind": "plsql_unit_needs_manual_review",
    "unit_kind": "PACKAGE",
    "name": "PKG_RATING"
  },
  {
    "kind": "plsql_unit_needs_manual_review",
    "unit_kind": "PACKAGE BODY",
    "name": "PKG_RATING"
  },
  {
    "kind": "plsql_unit_needs_manual_review",
    "unit_kind": "PACKAGE",
    "name": "PKG_INVOICING"
  },
  {
    "kind": "plsql_unit_needs_manual_review",
    "unit_kind": "PACKAGE BODY",
    "name": "PKG_INVOICING"
  },
  {
    "kind": "plsql_unit_needs_manual_review",
    "unit_kind": "PACKAGE",
    "name": "PKG_DUNNING"
  },
  {
    "kind": "plsql_unit_needs_manual_review",
    "unit_kind": "PACKAGE BODY",
    "name": "PKG_DUNNING"
  },
  {
    "kind": "trigger_business_logic",
    "table": "SUBSCRIPTIONS",
    "name": "TRG_SUBSCRIPTIONS_HIST"
  },
  {
    "kind": "trigger_business_logic",
    "table": "SUBSCRIPTIONS",
    "name": "TRG_SUB_NO_UNCANCEL"
  },
  {
    "kind": "trigger_business_logic",
    "table": "USAGE_EVENTS",
    "name": "TRG_USAGE_EVENTS_CHECK"
  },
  {
    "kind": "scheduler_job",
    "name": "JOB_NIGHTLY_DUNNING",
    "repeat_interval": "FREQ=DAILY;BYHOUR=2;BYMINUTE=0",
    "note": "batch logic lives in the database; needs an owner after migration"
  },
  {
    "kind": "scheduler_job",
    "name": "JOB_PURGE_AUDIT_LOG",
    "repeat_interval": "FREQ=DAILY;BYHOUR=3;BYMINUTE=30",
    "note": "batch logic lives in the database; needs an owner after migration"
  }
]
```

Reading: the nine `date_format_assumed` rows are the empty-profile text dates (`CUSTOMER_MASTER_HIST.*` six, `CUSTOMER_MASTER.LAST_INVOICE_DT/LAST_PAYMENT_DT/TERMINATE_DT`); the ten `plsql_unit_needs_manual_review` rows are the five packages × (spec, body); the three `trigger_business_logic` rows are the triggers the proposer could not close as identity triggers (`TRG_SUBSCRIPTIONS_HIST`, `TRG_SUB_NO_UNCANCEL`, `TRG_USAGE_EVENTS_CHECK`); the two `scheduler_job` rows are `JOB_NIGHTLY_DUNNING` and `JOB_PURGE_AUDIT_LOG`. `TRG_CUSTOMER_MASTER_HIST` is **not** in this list — see §5.

## 5. `modeling.answered`

```json
[
  {
    "kind": "trigger_business_logic",
    "table": "BILLING_AUDIT_LOG",
    "name": "TRG_BILLING_AUDIT_LOG_ID",
    "answered_by": "sequence_trigger_identity",
    "explanation": "the DDL census identifies this trigger as assigning a sequence-generated identity",
    "evidence": [
      {
        "kind": "ddl_census",
        "ref": "trigger TRG_BILLING_AUDIT_LOG_ID assigns NEXTVAL"
      }
    ]
  },
  {
    "kind": "trigger_business_logic",
    "table": "CUSTOMER_MASTER",
    "name": "TRG_CUSTOMER_MASTER_SEQ",
    "answered_by": "sequence_trigger_identity",
    "explanation": "the DDL census identifies this trigger as assigning a sequence-generated identity",
    "evidence": [
      {
        "kind": "ddl_census",
        "ref": "trigger TRG_CUSTOMER_MASTER_SEQ assigns NEXTVAL"
      }
    ]
  },
  {
    "kind": "trigger_business_logic",
    "table": "CUSTOMER_MASTER",
    "name": "TRG_CUSTOMER_MASTER_HIST",
    "answered_by": "sequence_trigger_identity",
    "explanation": "the DDL census identifies this trigger as assigning a sequence-generated identity",
    "evidence": [
      {
        "kind": "ddl_census",
        "ref": "trigger TRG_CUSTOMER_MASTER_SEQ assigns NEXTVAL"
      }
    ]
  },
  {
    "kind": "trigger_business_logic",
    "table": "ENTITY_ATTR_VALUE",
    "name": "TRG_ENTITY_ATTR_VALUE_SEQ",
    "answered_by": "sequence_trigger_identity",
    "explanation": "the DDL census identifies this trigger as assigning a sequence-generated identity",
    "evidence": [
      {
        "kind": "ddl_census",
        "ref": "trigger TRG_ENTITY_ATTR_VALUE_SEQ assigns NEXTVAL"
      }
    ]
  },
  {
    "kind": "date_format_assumed",
    "table": "CUSTOMER_MASTER",
    "column": "LAST_ACTIVITY_DT",
    "format": "%d-%b-%y",
    "conformance": 1.0,
    "evidence": "text_shapes:CUSTOMER_MASTER.LAST_ACTIVITY_DT"
  },
  {
    "kind": "date_format_assumed",
    "table": "ENTITY_ATTR_VALUE",
    "column": "CREATED_DT",
    "format": "%d-%b-%y",
    "conformance": 1.0,
    "evidence": "text_shapes:ENTITY_ATTR_VALUE.CREATED_DT"
  },
  {
    "kind": "date_format_assumed",
    "table": "INVOICE_HEADER",
    "column": "INVOICE_DT",
    "format": "%d-%b-%y",
    "conformance": 1.0,
    "evidence": "text_shapes:INVOICE_HEADER.INVOICE_DT"
  },
  {
    "kind": "date_format_assumed",
    "table": "INVOICE_HEADER",
    "column": "DUE_DT",
    "format": "%d-%b-%y",
    "conformance": 1.0,
    "evidence": "text_shapes:INVOICE_HEADER.DUE_DT"
  },
  {
    "kind": "date_format_assumed",
    "table": "INVOICE_LINE",
    "column": "INVOICE_DT",
    "format": "%d-%b-%y",
    "conformance": 1.0,
    "evidence": "text_shapes:INVOICE_LINE.INVOICE_DT"
  }
]
```

Third entry: `TRG_CUSTOMER_MASTER_HIST` is answered by `sequence_trigger_identity` citing `TRG_CUSTOMER_MASTER_SEQ`'s NEXTVAL. The DDL census lists `TRG_CUSTOMER_MASTER_HIST` as `AFTER … UPDATE OR DELETE` on `CUSTOMER_MASTER` with `sequence_assigns: []`; the answer is attributed to the wrong trigger (same table, different trigger). Recorded as a proposer defect for `05_decisions.md`; not edited.

## 6. Cardinality basis — `assumed` vs `derived`

`modeling.cardinality_default` = `assumed`. All 23 rationale rows:

| parent → child | rule | decision | basis | `basis_sources` | evidence refs |
|---|---|---|---|---|---|
| `CUSTOMER_MASTER` → `CUSTOMER_MASTER_HIST` (CUST_ID) | `pointer_only_no_fk` | reference | **assumed** | `["ddl"]` | `*_ID column with a matching table and no FK` |
| `TENANTS` → `CUSTOMER_MASTER_HIST` (TENANT_ID) | `pointer_only_no_fk` | reference | **assumed** | `["ddl"]` | `*_ID column with a matching table and no FK` |
| `TENANTS` → `CUSTOMER_MASTER` (TENANT_ID) | `pointer_only_no_fk` | reference | **assumed** | `["ddl"]` | `*_ID column with a matching table and no FK` |
| `CUSTOMER_MASTER` → `INVOICE_HEADER` (CUST_ID) | `pointer_only_no_fk` | reference | **assumed** | `["ddl"]` | `*_ID column with a matching table and no FK` |
| `TENANTS` → `INVOICE_HEADER` (TENANT_ID) | `pointer_only_no_fk` | reference | **assumed** | `["ddl"]` | `*_ID column with a matching table and no FK` |
| `INVOICE_HEADER` → `INVOICE_LINE` (INVOICE_ID) | `pointer_only_no_fk` | reference | **assumed** | `["ddl"]` | `*_ID column with a matching table and no FK` |
| `CUSTOMER_MASTER` → `INVOICE_LINE` (CUST_ID) | `pointer_only_no_fk` | reference | **assumed** | `["ddl"]` | `*_ID column with a matching table and no FK` |
| `TENANTS` → `INVOICE_LINE` (TENANT_ID) | `pointer_only_no_fk` | reference | **assumed** | `["ddl"]` | `*_ID column with a matching table and no FK` |
| `TENANTS` → `SUBSCRIPTIONS_HIST` (TENANT_ID) | `pointer_only_no_fk` | reference | **assumed** | `["ddl"]` | `*_ID column with a matching table and no FK` |
| `PLANS` → `SUBSCRIPTIONS_HIST` (PLAN_ID) | `pointer_only_no_fk` | reference | **assumed** | `["ddl"]` | `*_ID column with a matching table and no FK` |
| `TENANTS` → `RATING_PERIODS` (TENANT_ID) | `shared_child` | reference | **assumed** | `["ddl"]` | `ap-8e58932397`, `ap-8ee13949bc` |
| `RATING_PERIODS` → `INVOICES` (PERIOD_ID) | `shared_child` | reference | **derived** | `["ddl", "access"]` | `ap-0da411e03b`, `ap-75910aef55`, `ap-c026ebf3a8`, `ap-c43f1f14dc` |
| `TENANTS` → `INVOICES` (TENANT_ID) | `shared_child` | reference | **derived** | `["ddl", "access"]` | `ap-0da411e03b`, `ap-75910aef55`, `ap-c026ebf3a8`, `ap-c43f1f14dc` |
| `TENANTS` → `CREDIT_NOTES` (TENANT_ID) | `co_read` | embed | **derived** | `["ddl", "access"]` | `ap-41de3e5203`, `ap-2e59f9675d`, `ap-7a575dfc2d` |
| `PLANS` → `SUBSCRIPTIONS` (PLAN_ID) | `shared_child` | reference | **derived** | `["ddl", "access"]` | `ap-22fec4f2aa`, `ap-781940a6e5`, `ap-b6d8685d76`, `ap-a7af1a6156`, `ap-d3754b6b8a`, `ap-f95317f034` |
| `TENANTS` → `SUBSCRIPTIONS` (TENANT_ID) | `shared_child` | reference | **derived** | `["ddl", "access"]` | `ap-22fec4f2aa`, `ap-781940a6e5`, `ap-b6d8685d76`, `ap-d3754b6b8a`, `ap-f95317f034`, `ap-a7af1a6156` |
| `TENANTS` → `USAGE_EVENTS` (TENANT_ID) | `child_written_alone` | reference | **derived** | `["ddl", "access"]` | `ap-d0babb7b83` |
| `INVOICES` → `DUNNING_ATTEMPTS` (INVOICE_ID) | `read_by_parent_key` | embed | **derived** | `["ddl", "access", "data"]` | `embed_bytes:DUNNING_ATTEMPTS->INVOICES(INVOICE_ID)`, `fanout:DUNNING_ATTEMPTS->INVOICES(INVOICE_ID)`, `fk_integrity:DUNNING_ATTEMPTS->INVOICES(INVOICE_ID)`, `row_bytes:INVOICES`, `ap-37287a11b5`, `ap-68fdfcc880` |
| `TENANTS` → `DUNNING_ATTEMPTS` (TENANT_ID) | `lookup_reference` | reference | **derived** | `["ddl"]` | `ap-68fdfcc880` |
| `TENANTS` → `NOTIFICATIONS` (TENANT_ID) | `default` | reference | **assumed** | `["ddl"]` | `ap-7692fe1e9a` |
| `INVOICES` → `INVOICE_LINES` (INVOICE_ID) | `read_by_parent_key` | embed | **derived** | `["ddl", "access", "data"]` | `embed_bytes:INVOICE_LINES->INVOICES(INVOICE_ID)`, `fanout:INVOICE_LINES->INVOICES(INVOICE_ID)`, `fk_integrity:INVOICE_LINES->INVOICES(INVOICE_ID)`, `row_bytes:INVOICES`, `ap-620d0a2057`, `ap-56d46b7c81`, `ap-5c6c87e418` |
| `RATING_PERIODS` → `RATING_RESULTS` (PERIOD_ID) | `shared_child` | reference | **assumed** | `["ddl"]` | `ap-76af3595e0`, `ap-d7af986eeb` |
| `SUBSCRIPTIONS` → `RATING_RESULTS` (SUBSCRIPTION_ID) | `shared_child` | reference | **assumed** | `["ddl"]` | `ap-76af3595e0`, `ap-d7af986eeb` |

**Tables whose cardinality is `assumed`** (14 rows, 8 child tables): `CUSTOMER_MASTER`, `CUSTOMER_MASTER_HIST`, `INVOICE_HEADER`, `INVOICE_LINE`, `NOTIFICATIONS`, `RATING_PERIODS`, `RATING_RESULTS`, `SUBSCRIPTIONS_HIST`.

- The ten `pointer_only_no_fk` rows are `assumed` by construction (`basis_sources: ["ddl"]`, no profile fan-out).
- `TENANTS → RATING_PERIODS`, `RATING_PERIODS → RATING_RESULTS`, `SUBSCRIPTIONS → RATING_RESULTS` are `shared_child` but `assumed`: the cited patterns are rated but the profile fan-out for these pairs was not used as basis.
- `TENANTS → NOTIFICATIONS` is the only `default` row (`ap-7692fe1e9a`, a `cold` read), `assumed`.
- `derived` (9): `RATING_PERIODS → INVOICES`, `TENANTS → INVOICES`, `TENANTS → CREDIT_NOTES`, `PLANS → SUBSCRIPTIONS`, `TENANTS → SUBSCRIPTIONS`, `TENANTS → USAGE_EVENTS`, `INVOICES → DUNNING_ATTEMPTS`, `TENANTS → DUNNING_ATTEMPTS`, `INVOICES → INVOICE_LINES`.

## 7. `modeling.application_evidence`

```json
{
  "confirmed_patterns": 64,
  "files": [
    "etl/legacy-extra/tools/oracle_custbill_extract.py",
    "services/legacy-billing/app/backends/oracle.py",
    "services/legacy-billing/app/facade.py",
    "services/legacy-billing/app/reports.py",
    "services/legacy-billing/db/oracle/packages/01_pkg_util.sql",
    "services/legacy-billing/db/oracle/packages/02_pkg_plans.sql",
    "services/legacy-billing/db/oracle/packages/03_pkg_rating.sql",
    "services/legacy-billing/db/oracle/packages/04_pkg_invoicing.sql",
    "services/legacy-billing/db/oracle/packages/05_pkg_dunning.sql",
    "services/legacy-billing/db/oracle/schema/01_tables.sql",
    "services/legacy-billing/db/oracle/schema/02_horror.sql",
    "services/legacy-billing/db/oracle/schema/04_jobs.sql"
  ]
}
```

`confirmed_patterns: 64` = the 90 confirmed patterns of `03_access_review.md` minus the 26 confirmed `deploy_script: true` rows. Five of the twelve files are the packages (`01_pkg_util.sql` … `05_pkg_dunning.sql`). Rationale rows whose evidence resolves to a package or trigger routine:

- `TENANTS → RATING_PERIODS` (`shared_child`): `ap-8e58932397` → `pkg_rating.sp_finalize_rating` (`services/legacy-billing/db/oracle/packages/03_pkg_rating.sql`); `ap-8ee13949bc` → `pkg_rating.sp_finalize_rating` (`services/legacy-billing/db/oracle/packages/03_pkg_rating.sql`)
- `RATING_PERIODS → INVOICES` (`shared_child`): `ap-75910aef55` → `pkg_invoicing.sp_issue_invoice` (`services/legacy-billing/db/oracle/packages/04_pkg_invoicing.sql`); `ap-c026ebf3a8` → `pkg_invoicing.sp_issue_invoice` (`services/legacy-billing/db/oracle/packages/04_pkg_invoicing.sql`); `ap-c43f1f14dc` → `pkg_invoicing.sp_issue_invoice` (`services/legacy-billing/db/oracle/packages/04_pkg_invoicing.sql`)
- `TENANTS → INVOICES` (`shared_child`): `ap-75910aef55` → `pkg_invoicing.sp_issue_invoice` (`services/legacy-billing/db/oracle/packages/04_pkg_invoicing.sql`); `ap-c026ebf3a8` → `pkg_invoicing.sp_issue_invoice` (`services/legacy-billing/db/oracle/packages/04_pkg_invoicing.sql`); `ap-c43f1f14dc` → `pkg_invoicing.sp_issue_invoice` (`services/legacy-billing/db/oracle/packages/04_pkg_invoicing.sql`)
- `TENANTS → CREDIT_NOTES` (`co_read`): `ap-2e59f9675d` → `pkg_invoicing.compute_preview` (`services/legacy-billing/db/oracle/packages/04_pkg_invoicing.sql`); `ap-41de3e5203` → `pkg_invoicing.compute_preview` (`services/legacy-billing/db/oracle/packages/04_pkg_invoicing.sql`); `ap-7a575dfc2d` → `pkg_invoicing.sp_issue_invoice` (`services/legacy-billing/db/oracle/packages/04_pkg_invoicing.sql`)
- `PLANS → SUBSCRIPTIONS` (`shared_child`): `ap-22fec4f2aa` → `pkg_rating.compute_rating` (`services/legacy-billing/db/oracle/packages/03_pkg_rating.sql`); `ap-781940a6e5` → `pkg_plans.sp_change_plan` (`services/legacy-billing/db/oracle/packages/02_pkg_plans.sql`); `ap-a7af1a6156` → `pkg_plans.sp_change_plan` (`services/legacy-billing/db/oracle/packages/02_pkg_plans.sql`); `ap-b6d8685d76` → `pkg_rating.sp_finalize_rating` (`services/legacy-billing/db/oracle/packages/03_pkg_rating.sql`); `ap-d3754b6b8a` → `pkg_dunning.sp_suspend_overdue` (`services/legacy-billing/db/oracle/packages/05_pkg_dunning.sql`)
- `TENANTS → SUBSCRIPTIONS` (`shared_child`): `ap-22fec4f2aa` → `pkg_rating.compute_rating` (`services/legacy-billing/db/oracle/packages/03_pkg_rating.sql`); `ap-781940a6e5` → `pkg_plans.sp_change_plan` (`services/legacy-billing/db/oracle/packages/02_pkg_plans.sql`); `ap-a7af1a6156` → `pkg_plans.sp_change_plan` (`services/legacy-billing/db/oracle/packages/02_pkg_plans.sql`); `ap-b6d8685d76` → `pkg_rating.sp_finalize_rating` (`services/legacy-billing/db/oracle/packages/03_pkg_rating.sql`); `ap-d3754b6b8a` → `pkg_dunning.sp_suspend_overdue` (`services/legacy-billing/db/oracle/packages/05_pkg_dunning.sql`)
- `INVOICES → DUNNING_ATTEMPTS` (`read_by_parent_key`): `ap-37287a11b5` → `pkg_dunning.sp_schedule_dunning` (`services/legacy-billing/db/oracle/packages/05_pkg_dunning.sql`); `ap-68fdfcc880` → `pkg_dunning.sp_schedule_dunning` (`services/legacy-billing/db/oracle/packages/05_pkg_dunning.sql`)
- `TENANTS → DUNNING_ATTEMPTS` (`lookup_reference`): `ap-68fdfcc880` → `pkg_dunning.sp_schedule_dunning` (`services/legacy-billing/db/oracle/packages/05_pkg_dunning.sql`)
- `TENANTS → NOTIFICATIONS` (`default`): `ap-7692fe1e9a` → `pkg_dunning.sp_suspend_overdue` (`services/legacy-billing/db/oracle/packages/05_pkg_dunning.sql`)
- `INVOICES → INVOICE_LINES` (`read_by_parent_key`): `ap-56d46b7c81` → `pkg_invoicing.sp_issue_invoice` (`services/legacy-billing/db/oracle/packages/04_pkg_invoicing.sql`); `ap-5c6c87e418` → `pkg_invoicing.sp_issue_invoice` (`services/legacy-billing/db/oracle/packages/04_pkg_invoicing.sql`); `ap-620d0a2057` → `pkg_invoicing.fn_invoice_lines` (`services/legacy-billing/db/oracle/packages/04_pkg_invoicing.sql`)
- `RATING_PERIODS → RATING_RESULTS` (`shared_child`): `ap-76af3595e0` → `pkg_rating.sp_finalize_rating` (`services/legacy-billing/db/oracle/packages/03_pkg_rating.sql`); `ap-d7af986eeb` → `pkg_rating.sp_finalize_rating` (`services/legacy-billing/db/oracle/packages/03_pkg_rating.sql`)
- `SUBSCRIPTIONS → RATING_RESULTS` (`shared_child`): `ap-76af3595e0` → `pkg_rating.sp_finalize_rating` (`services/legacy-billing/db/oracle/packages/03_pkg_rating.sql`); `ap-d7af986eeb` → `pkg_rating.sp_finalize_rating` (`services/legacy-billing/db/oracle/packages/03_pkg_rating.sql`)

Package-sourced patterns that are confirmed but cited by **no** rationale, index or question: `ap-779ce5b5b7` (`pkg_ow_util.log_msg` → BILLING_AUDIT_LOG), `ap-d9d4207c37` (`pkg_ow_util.f_code_desc` → CODES), `ap-d3754b6b8a` (`pkg_dunning.sp_suspend_overdue` UPDATE SUBSCRIPTIONS with cascade to `trg_subscriptions_hist`) — the latter is the second of the three UPDATEs the review counted for `written_together` (§2.6).

## 8. Index candidates — all collections, and `modeling.dropped_indexes`

- `ratingPeriods` (RATING_PERIODS): `[["tenantId", 1], ["periodStart", 1]]` unique [natural_key: ap-81929b0d21]
- `customerMasterHist` (CUSTOMER_MASTER_HIST): `[]`
- `invoices` (INVOICES): `[["tenantId", 1], ["issuedAt", 1], ["_id", 1]]` [access: ap-0da411e03b, ap-15404b0226, ap-46a8eb988b]; `[["_id", 1], ["tenantId", 1]]` [access: ap-0da411e03b]; `[["dunningAttempts.scheduledFor", 1]]` [access: ap-0a1051eac3]; `[["lines.lineNo", 1]]` [access: ap-620d0a2057]; `[["statusCd", 1], ["issuedAt", 1], ["_id", 1]]` [access: ap-46a8eb988b]; `[["periodId", 1]]` [reference_fk: ap-15404b0226]
- `codes` (CODES): `[["codeDesc", 1], ["codeType", 1]]` [access: ap-6470faec0f]; `[["codeType", 1], ["codeVal", 1]]` [access: ap-0a1051eac3, ap-15404b0226, ap-3fbad6ec1e, ap-88f22eaf5b, ap-d9d4207c37, ap-fe087c4e0c]
- `tenants` (TENANTS): `[["creditNotes.remainingAmount", 1]]` [access: ap-2e59f9675d]; `[["creditNotes.issuedOn", 1], ["creditNotes.id", 1], ["creditNotes.remainingAmount", 1]]` [access: ap-b259650bfe]; `[["name", 1]]` unique [natural_key: ]
- `plans` (PLANS): `[["monthlyFee", 1], ["_id", 1]]` [access: ap-b720c4157e]; `[["monthlyFee", 1], ["code", 1]]` [access: ap-33e1dc2584]; `[["code", 1]]` unique [natural_key: ]
- `subscriptions` (SUBSCRIPTIONS): `[["tenantId", 1], ["endsOn", 1], ["startsOn", 1]]` [access: ap-160686ae25, ap-1fe02141ee, ap-22fec4f2aa, ap-2cc202a47e, ap-60ec05ff91, ap-781940a6e5, ap-95a0f9e481, ap-b6d8685d76, ap-df26fbfed9, ap-ee373ebbd1]; `[["endsOn", 1], ["startsOn", 1]]` [access: ap-60ec05ff91, ap-95a0f9e481]; `[["planId", 1]]` [reference_fk: ap-df26fbfed9, ap-60ec05ff91, ap-95a0f9e481, ap-ee373ebbd1, ap-160686ae25]
- `usageEvents` (USAGE_EVENTS): `[["tenantId", 1], ["occurredAt", 1]]` [access: ap-2b3995792f, ap-3fbad6ec1e, ap-61c2839e36]
- `notifications` (NOTIFICATIONS): `[["tenantId", 1], ["kindCd", 1], ["sentAt", 1]]` unique [natural_key: ]
- `customerMaster` (CUSTOMER_MASTER): `[["tenantId", 1], ["custSeqNo", 1]]` [access: ap-bd510b9356, ap-e45fe9768e]
- `entityAttrValue` (ENTITY_ATTR_VALUE): `[["entityId", 1], ["_id", 1]]` [access: ap-6c1786cb2d]
- `invoiceHeader` (INVOICE_HEADER): `[]`
- `invoiceLine` (INVOICE_LINE): `[]`
- `billingAuditLog` (BILLING_AUDIT_LOG): `[]`
- `subscriptionsHist` (SUBSCRIPTIONS_HIST): `[]`
- `ratingResults` (RATING_RESULTS): `[["periodId", 1]]` [reference_fk: ap-81929b0d21]

`modeling.dropped_indexes` (DDL indexes the proposer dropped as a left prefix of a planned index):

```json
[
  {
    "table": "RATING_PERIODS",
    "columns": [
      "TENANT_ID"
    ],
    "reason": "left prefix of planned index"
  },
  {
    "table": "INVOICES",
    "columns": [
      "TENANT_ID"
    ],
    "reason": "left prefix of planned index"
  },
  {
    "table": "CODES",
    "columns": [
      "CODE_TYPE"
    ],
    "reason": "left prefix of planned index"
  },
  {
    "table": "SUBSCRIPTIONS",
    "columns": [
      "TENANT_ID"
    ],
    "reason": "left prefix of planned index"
  },
  {
    "table": "USAGE_EVENTS",
    "columns": [
      "TENANT_ID"
    ],
    "reason": "left prefix of planned index"
  }
]
```

## 9. Contradictions and gaps against `03_access_review.md` (recorded, not fixed)

1. **`SUBSCRIPTIONS → SUBSCRIPTIONS_HIST` has no rationale row; `written_together`/`via_trigger` absent** although three confirmed, pinned UPDATEs carry `cascades: ["ap-bdfdef0db0"]` (review check 1, §3 consequences). Cause: `SUBSCRIPTIONS_HIST.ID` is not a `*_ID` column, so no census pointer/edge exists and the rule order never ran (§2.6).
2. **`CUSTOMER_MASTER → CUSTOMER_MASTER_HIST` fired `pointer_only_no_fk`, not `default`/`ownership`** as the review expected (check 2). No `written_together` — agrees (§2.8).
3. **`TRG_CUSTOMER_MASTER_HIST` closed as `sequence_trigger_identity`** on another trigger's evidence (§5); the review established it is a full-row history-copy trigger.
4. **`ENTITY_ATTR_VALUE` ownership**: the review established the owner (`CUSTOMER_MASTER`, two-statement read keyed by `cust_id`, `observed_types: ["CUSTOMER"]`); the spec keeps "separate collection until ownership is known" with no edge (§2.3).
5. **`*_CD` → `CODES` proposals rest on value-domain overlap**, while the review shows packages use inline `DECODE` and no `CUSTOMER_MASTER.*_CD` is ever joined (§2.4). `DUNNING_ATTEMPTS.STATUS_CD`, which *is* joined by the app, has no `code_lookup` question.
6. **`SUBSCRIPTIONS_HIST.HIST_DT` format pinned to `%Y%m%d` at `conformance 0.0`** (internal inconsistency, §2.6).
7. **`BILLING_AUDIT_LOG` detached-writer semantics and `INVOICES`+`INVOICE_LINES`/`RATING_*`/`CREDIT_NOTES` single-transaction facts** (review §3.3) are not in the JSON — expected, since the scanner emits no `txn`; `05_decisions.md` must carry them.
8. **`INVOICE_HEADER → INVOICE_LINE`**: agrees with the review (reference, no per-parent evidence; `INVOICE_LINE` ≠ `INVOICE_LINES`). Only new fact: 37/1500 `INVOICE_ID` values unresolved against `INVOICE_HEADER` (§2.2).

## 10. Pre-PR self-check (`.agents/skills/tp-pre-pr-self-check`)

This step produces documentation and a generated JSON; it writes to no database and runs no load, so most items are not applicable and are recorded as such rather than as green.

| item | status |
|---|---|
| NULL / missing attribution cannot fail open | n/a (no load); the spec's `null_missing_equiv` canonicalization rule and the `date_format_nonconforming` quarantine proposals are listed, not applied |
| every catalog/schema/collection/table reference scoped to the unit namespace (`ow_tp` / `ow-tp-`) | n/a — no target namespace is created; the spec names collections only (`customerMaster`, …), the database is fixed by `.migration/allowed_targets.json` (`mmp_rt_b4_oracle`) in later steps |
| no DDL drops/replaces/alters a shared table | true — no DDL executed; legacy source untouched (`git status` shows only `.migration/` changes) |
| retention / cleanup safe on rerun | n/a — nothing cleaned |
| cleanup retains evidence and recon artifacts | n/a; evidence retained: `mapping_spec.json`, this review |
| no secrets, tokens, real addresses in source/evidence/history | true — a case-insensitive grep over `mapping_spec.json` and this file for Atlas connection-string prefixes, credential keywords and e-mail addresses finds nothing; the only secret is referenced by name (`MONGODB_ATLAS_URI`) |
| parity-vs-tolerance decision matches the contract | n/a — no recon in this step |
| idempotency proven by actual rerun | **partially**: the proposer was run twice; a second run from a different cwd reproduced identical modeling output but different `modeling.*.path` provenance strings (relative to cwd), so the committed artifact is the run-branch-root run. Byte-identical rerun from the root was not separately executed |
| recon values recomputed from the target platform | n/a — no target platform touched |
| every unverified / untested path listed | §4 (`modeling.unresolved`), §6 (`assumed` rows), §9 |
| recon report `"kind": "recon-report"` as `*.recon.json` | n/a — no recon report in this step |
| capability preflight passed for every required path | n/a — no live path (`offline_guard.py` not needed; no DSN used) |
| `make tp-smoke` green | **true** — `tp-smoke: all checks passed` (the first invocation failed before any check on an untrusted `mise.toml` in the VM; `mise trust` then re-run; nothing in the repo changed) |

