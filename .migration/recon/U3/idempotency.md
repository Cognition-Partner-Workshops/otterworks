# U3 loader idempotency

Both reruns used the same loader command and secret names; secret values are intentionally not recorded.

## Commands

```sh
export OW_PG_DSN='<fixture DSN assigned to OW_PG_DSN>'
python3 scripts/tp_mongo/load_u3.py | tee .migration/recon/U3/load_run1.log
cp .migration/recon/U3/load_report.json .migration/recon/U3/load_report_run1.json
python3 scripts/tp_mongo/load_u3.py | tee .migration/recon/U3/load_run2.log
```

## Results

| Run | documents | document_snapshots | orphan_document_snapshots | embedded_versions |
|---|---:|---:|---:|---:|
| 1 | 2000 | 384 | 6 | 13876 |
| 2 | 2000 | 384 | 6 | 13876 |

Each run dropped and recreated all three owned collections:

- `ow_tp_mongodb_205236.documents`
- `ow_tp_mongodb_205236.document_snapshots`
- `ow_tp_mongodb_205236_quarantine.orphan_document_snapshots`

U0 collections were checked before run 1 and after run 2; they were untouched and counts were unchanged:

- Before run 1: `plans=3`, `tenants=69`, `codes=32`
- After run 2: `plans=3`, `tenants=69`, `codes=32
