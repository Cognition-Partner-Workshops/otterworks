# Reconciliation tolerance contract

Version: `v1-proposed`

Source profile: `oracle`

Recommended recon mode: `LIVE`

No row below is approved until STOP A is recorded.

| Surface | Proposed contract | Status |
|---|---|---|
| `NUMBER(p,0)`, `p <= 18` | BSON integer/long; exact equality and exact aggregate sums | PROPOSED — recommended |
| Scaled or unbounded `NUMBER` | Decimal128; preserve declared scale, compare after half-even Decimal128 canonicalization, zero unexplained numeric delta | PROPOSED — recommended |
| `FLOAT` / binary float types | BSON double; exact counts and profile-driven numeric canonicalization; any non-zero tolerance requires a new approval | PROPOSED — recommended |
| Oracle `DATE` | Interpret with pinned source session timezone UTC, convert to UTC BSON date, millisecond precision | PROPOSED — recommended |
| Oracle `TIMESTAMP*` | Convert to UTC and truncate sub-millisecond digits; preserve original zone in a sibling field only when the census finds a consumer | PROPOSED — recommended |
| `CHAR` | Strip Oracle blank padding before comparison | PROPOSED — recommended |
| Empty Oracle string | Store as explicit BSON `null`, matching Oracle empty-string-is-NULL semantics | PROPOSED — recommended |
| Null vs missing | Distinct; missing is not equivalent to explicit null unless a mapping row explicitly declares an optional field | PROPOSED — recommended |
| String comparison | Binary/case-sensitive after `CHAR` trimming; add collation case-folding only where the census proves an NLS-insensitive access path | PROPOSED — recommended |
| `CLOB` / `BLOB` / `XMLTYPE` | No truncation; objects approaching 16 MB require a STOP B storage decision | PROPOSED — recommended |
| Root row/document counts | Zero tolerance | PROPOSED — recommended |
| Embedded child cardinality | Exact equality between source child rows and summed target array lengths, excluding only explicitly quarantined source keys | PROPOSED — recommended |
| Keyed field diffs | Zero unexplained mismatches | PROPOSED — recommended |
| Quarantine | Zero silent drops; every quarantined source record must have a reason and remain included in coverage arithmetic | PROPOSED — recommended |
| Tier 4 behavior | Representative operation outputs and side effects must match exactly after the canonicalization above | PROPOSED — recommended |

## Size tiers and sampling

| Setting | Proposed value | Status |
|---|---|---|
| Full keyed diff threshold | `100,000` root documents per unit | PROPOSED — recommended |
| Above-threshold keyed sample | Deterministic stratified sample of `10,000` keys plus full counts and aggregates | PROPOSED — recommended |
| Seed | Unit contract supplies a fixed integer and records it in `result.json` | PROPOSED — recommended |
| Source-load cap | `1` concurrent extract/recon query until the source owner approves a higher value | PROPOSED — conservative |
| Pilot fan-out width | Up to `5` units, still bounded by source-load cap | PROPOSED — recommended |
| Later fan-out width | Up to `20` sessions, still bounded by source-load cap and write-target isolation | PROPOSED — recommended |
| Full end-to-end re-run cap | `3` per unit, then halt and escalate | PROPOSED — recommended |
| Parallel-run green streak | `3` complete source cycles; `5` for money-moving or procedure-heavy paths | PROPOSED — recommended |

## Evidence-integrity rules

1. Every gate declares its source and target population, including namespace/watermark filters.
2. No child may grade data it generated as source truth.
3. Counts, rates, and quarantine percentages use the declared source population as denominator.
4. The harness receives the Oracle profile's canonicalization rules verbatim, with the two STOP A placeholders resolved by this contract.
5. `result.json` is the merge authority; summaries and accelerator output are not.
6. LIVE evidence requires simultaneous source and target access. SNAPSHOT evidence is scoped to its manifest and requires customer-run in-perimeter recon before STOP C.

## Amendment procedure

After STOP A this file becomes versioned and append-only. Any tolerance change requires a
new explicit approval in `05_decisions.md`, a new version label, and a recorded
re-verification scope for already merged units and waves.
