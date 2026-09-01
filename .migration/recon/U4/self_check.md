# U4 pre-PR self-check (.agents/skills/tp-pre-pr-self-check)

Run 2026-09-01 (UTC), fixture mode. Evidence paths are relative to the repo root.

- [x] NULL/missing attribution: `folder_id` carries `null_missing_equiv` and is deferred to
      Tier 3 by the harness (result.json tier2 `deferred_to_tier3`); absent DynamoDB
      attributes load as BSON null, never silently defaulted. Missing `s3_key` marks the
      item `orphaned_metadata` (fail-closed).
- [x] Scoping: all writes go to `ow_tp_mongodb_205236.files` only; quarantine database untouched.
- [x] No DDL on shared objects: DynamoDB is read-only (Scan, ConsistentRead); the only drop
      is `files` in the registered target database.
- [x] Rerun safety: drop+recreate of `files` only; a newer run would use its own database.
- [x] Cleanup retains evidence: load reports, gate result/report/summary, mapping copy kept.
- [x] Secrets: `MONGODB_ATLAS_URI` referenced by name; LocalStack `test/test` are the
      documented fixture placeholders; no emails/DL addresses in source or evidence.
- [x] Parity vs tolerance: mapping v1.0 + tolerance v1 as frozen; no shapes changed.
      Unit selection for the harness is a filtered copy (`mapping/u4.json`), not an edit.
- [x] Idempotency proven by actual rerun: `load_report.rerun.json`
      (`collection_existed_before: true`, `docs_before_drop: 10000`, after: 10000).
- [x] Recon values recomputed from target: harness run `gate/result.json`; the recon-report
      view (`docs/tech-partnerships/recon/U4.recon.json`) recounts ns tags, orphan markers,
      indexes via pymongo at generation time.
- [x] Unverified paths listed: `U4.recon.json` `unverified_paths` (4 entries).
- [x] Machine-readable report: `docs/tech-partnerships/recon/U4.recon.json` declares
      `"kind": "recon-report"`; `make tp-validate-recon FILE=...` -> PASS.
- [x] Capability preflight: manifest sha256 matched the run contract before extraction;
      LocalStack :4566 reachable; Atlas write to the registered db verified by load.
- [x] `make tp-smoke` green ("tp-smoke: all checks passed").
