# MongoDB run reconciliation — NS=demo1

Three-way diff: Atlas `ow_tp_demo1` vs Oracle OW_BILLING (batch 23746131) vs `testdata/legacy/manifests/demo1.json`. All values recomputed at report time.

| check                          | expected                         | actual                           | result |
|--------------------------------|----------------------------------|----------------------------------|--------|
| oracle_customer_rows           | 25000                            | 25000                            | PASS   |
| oracle_customer_checksum       | 0896d8fd769c66e47c8ba879cce919ac | 0896d8fd769c66e47c8ba879cce919ac | PASS   |
| oracle_invoice_header_rows     | 18750                            | 18750                            | PASS   |
| oracle_invoice_line_rows       | 150000                           | 150000                           | PASS   |
| oracle_invoice_line_checksum   | b890dd3d9d3dbefc888902ead3bef654 | b890dd3d9d3dbefc888902ead3bef654 | PASS   |
| oracle_eav_rows                | 8333                             | 8333                             | PASS   |
| atlas_customer_documents       | 25000                            | 25000                            | PASS   |
| atlas_customer_checksum        | 0896d8fd769c66e47c8ba879cce919ac | 0896d8fd769c66e47c8ba879cce919ac | PASS   |
| atlas_invoice_documents        | 18750                            | 18750                            | PASS   |
| atlas_line_conservation        | 150000                           | 150000                           | PASS   |
| atlas_line_checksum            | b890dd3d9d3dbefc888902ead3bef654 | b890dd3d9d3dbefc888902ead3bef654 | PASS   |
| atlas_eav_accounting           | 8333                             | 8333                             | PASS   |
| atlas_no_row_lost              | 25000                            | 25000                            | PASS   |
| atlas_no_null_valued_fields    | 0                                | 0                                | PASS   |
| anomaly_orphan_invoice_lines   | 37                               | 37                               | PASS   |
| anomaly_orphan_lines_in_source | 37                               | 37                               | PASS   |
| anomaly_dirty_signup_dates     | 50                               | 50                               | PASS   |
| anomaly_malformed_csv_lists    | 31                               | 31                               | PASS   |
| no_missing_required_key_rows   | 0                                | 0                                | PASS   |
| idempotency_rerun_converges    | 8c7a6a1545a28217d90627cc49dd0ec9 | 8c7a6a1545a28217d90627cc49dd0ec9 | PASS   |

Idempotency rerun: **PASS** — Both migrations were rerun against batch 23746131 after a snapshot of every recomputed target value (counts, checksums, quarantine breakdowns); the post-rerun recomputation is identical. customers 25000 -> 25000, lines accounted 150000 -> 150000, customers checksum unchanged, lines checksum unchanged.
