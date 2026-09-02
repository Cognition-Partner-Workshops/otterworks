# U6 pre-PR self-check

Skill: `.agents/skills/tp-pre-pr-self-check/SKILL.md`
Unit: U6

| Check | Result | Evidence / coverage |
|---|---|---|
| NULL and missing attribution cannot fail open | PASS | U6 replay report has matching `ns`-tagged counts for all 12 collections; `f_code_desc` missing-code behavior is covered by app-side unit tests. |
| Target references are unit-scoped and prefixed | PASS | Replay targets are `replay_u6_*` in `load_replay_u6.py`; report target DB is `ow_tp_mongodb_205236`; golden verification is recorded in `golden_untouched.txt`. |
| No DDL drops/replaces/alters shared tables | PASS | Loader staging swaps and dropTarget operations are guarded to `replay_u6_*` names only. |
| Rerun cleanup is safe and does not remove newer-run data | PASS | Two actual loads completed; `u6.recon.json` reports idempotency `pass`. |
| Cleanup retains run evidence and recon artifacts | PASS | `load_report.run1.json`, `load_report.json`, `result.json`, `tier4_replay.json`, and `u6.recon.json` are present. |
| No secrets, tokens, or real distribution-list/email addresses | PASS | URI/password pattern scan: `PASS no URI/password values found`; commit subjects contain no secrets. |
| Parity-versus-tolerance decision matches contract | PASS | `result.json` reports mapping `v1.0.1`, tolerance `v1`, verdict `PASS`; no tolerance changes were made. |
| Idempotency proven by actual rerun | PASS | Run1/run2 load reports compare equal; report idempotency result is `pass`. |
| Recon values recomputed from target platform | PASS | Report sets `values_recomputed_from_target: true`; replay counts are Atlas `count_documents` results. |
| Every unverified/untested path is listed | PASS | Six exact entries are present in `u6.recon.json`. |
| Recon report schema and artifact | PASS | `u6.recon.json` declares `kind: recon-report`; `make tp-validate-recon` passed. |
| Capability preflight | PASS | `recon_u6.py` runs `preflight_baseline` before `run_recon`; recorded recon result is PASS for tiers 1-4. |
| `make tp-smoke` | PASS | `/home/ubuntu/u6_evidence/tp-smoke.txt` reports `tp-smoke: all checks passed`. |

Contractual coverage gaps remain explicitly listed in `u6.recon.json`, including the LIVE-mode parent gate, HTTP-vs-entrypoint coverage, strict date parsing shape, concurrent plan changes, and `f_code_desc` caller coverage.
