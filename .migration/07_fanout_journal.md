# 07 — Fan-out journal (dynamic workflow)

| Run id | Launched (UTC) | Scope | State |
|---|---|---|---|
| `wfr-2defeb1f434347a8a9897c0bea356bcc` | 2026-09-01 21:58 | waves 0–3, units U0–U9 | pass 1 ended: U0 ESCALATE → resumed child finished GREEN (PR #1423; pass 2 re-ingests evidence), U3 MERGED, U4 held (LIVE re-recon of head pending), U1/U2/U5–U9 deferred on deps. Resume with the same run_id; recorded GREEN results replay. |

Child sessions: U0 devin-4a712cd3cdda4e22add668ce6fa915ca · U3 devin-b5ab105b3b5e42c98dcbf6a2379d068a · U4 devin-b6bf95838a094f438e146e101ebcbfdb

Pass 3 (same run id): waves 0, 2a, 2b, 3 CLOSED; U1 merged; U2 (#1432) merge BLOCKED on conflicts with U1 → original U2 child resumed by message, re-merged run branch (head 9e73ffea, fixture recon PASS). Pass 4 re-attests U2 LIVE and closes wave 1. Children: U1 devin-c386ebd61e8147549edb7c17e4ca6f35 · U2 devin-663f09e932ba4eacbed5b0635a1ba5d4 · U5 devin-30983324e6f94810b28254d0eb4a4dd0 · U6 devin-a3de8060beb04b54bad91d46c338805d · U7 devin-1522d2f15a5446fdb042c65df4576d28 · U8 devin-679bc1c8bf64427fb4d653ee0a9633ac · U9 devin-af044d06a64e4874b07e47e7cd8eb1a3

Phase 4 cutover-prep workflow `wfr-a41bb14dc4984d5fa6d995bd32685c83` (`.migration/cutover_workflow.py`): parallel-run GREEN 3/3 @ `0150de08`; evidence pack INCOMPLETE (PR #1455) → HALT → human "fix and re-gate" (decision 19). Original U8 child `devin-679bc1c8bf64427fb4d653ee0a9633ac` resumed by message → fix PR #1457 (`--u8-fix`, head `ba3b9034`, fixture recon PASS; it rewrote two U7 `test_log_msg_*` tests that asserted the retired `SEQ_BILLING_AUDIT_LOG/value` contract to the spec'd U1/D11 `counters` shape — flagged for the independent recon). Workflow resumed with FIX set: fix-recon-merge → parallel-run-v2 → evidence-pack-runbook-v2 → independent-audit.
