# U2 loader idempotency

Both reruns use the same loader command and secret names; secret values are intentionally not recorded.

## Sibling-collection snapshot before run 1

| Database / collection | Count |
|---|---:|
| `ow_tp_mongodb_205236.codes` | 32 |
| `ow_tp_mongodb_205236.tenants` | 69 |
| `ow_tp_mongodb_205236.plans` | 3 |
| `ow_tp_mongodb_205236.documents` | 2000 |
| `ow_tp_mongodb_205236.document_snapshots` | 384 |
| `ow_tp_mongodb_205236.files` | 10000 |
| `ow_tp_mongodb_205236_quarantine.orphan_document_snapshots` | 6 |

Expected sibling counts matched before run 1: `True`.

## Commands

```sh
export OW_BILLING_FIXTURE_DSN='<fixture DSN assigned to OW_BILLING_FIXTURE_DSN>'
python3 scripts/tp_mongo/load_u2.py 2>&1 | tee .migration/recon/U2/load_run1.log
cp .migration/recon/U2/load_report.json .migration/recon/U2/load_report_run1.json
python3 scripts/tp_mongo/load_u2.py 2>&1 | tee .migration/recon/U2/load_run2.log
```

## Sibling-collection snapshot after run 2

| Database / collection | Count |
|---|---:|
| `ow_tp_mongodb_205236.codes` | 32 |
| `ow_tp_mongodb_205236.tenants` | 69 |
| `ow_tp_mongodb_205236.plans` | 3 |
| `ow_tp_mongodb_205236.documents` | 2000 |
| `ow_tp_mongodb_205236.document_snapshots` | 384 |
| `ow_tp_mongodb_205236.files` | 10000 |
| `ow_tp_mongodb_205236_quarantine.orphan_document_snapshots` | 6 |

Expected sibling counts matched after run 2: `True`.

## U2 load comparison

| Run | invoices | embedded lines | quarantined lines | max lines per invoice | indexes |
|---|---:|---:|---:|---:|---|
| 1 | 18750 | 149963 | 37 | 23 | `batch_no_1_status_cd_1, cust_id_1, lines.line_id_1` |
| 2 | 18750 | 149963 | 37 | 23 | `batch_no_1_status_cd_1, cust_id_1, lines.line_id_1` |

`quarantined_line_ids` identical across run 1 and run 2: `True`.
