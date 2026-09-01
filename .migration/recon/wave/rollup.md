# Wave rollup — `customers` (wave 1) + `invoices` (wave 2)

Independent re-verification of both merged units in ONE uncontended window, run after all
unit-level loading was quiesced. Unit-level green did not carry over: every number below
comes from a fresh run in this window, not from the per-unit evidence the PRs carried.

- Window: 2026-09-01T02:01:27Z → 2026-09-01T02:01:51Z (wave recon),
  2026-09-01T01:59:32Z → 2026-09-01T02:00:06Z (parallel-run cycles),
  2026-09-01T02:03Z (embedded-child verification)
- Mode `live` (wave recon) / `continuous` (cycles) · mapping `1.0.0` · tolerances `1`
- Source concurrency `1` (STOP A cap) · harness: vendored pinned copy,
  `.migration/vendor/mongo-recon-harness` (H1 fix only)

## Wave verdict: **PASS**

| Unit | Verdict | T1 counts | T2 aggregates | T3 keyed diffs | T4 parity | Evidence |
|---|---|---|---|---|---|---|
| `customers` | **PASS** | 2 PASS | 42 PASS | 25,000 PASS | 2 PASS | `.migration/recon/wave/1/customers/result.json`, `report.md`, `recon.summary.md` |
| `invoices` | **PASS** | 2 PASS | 9 PASS | 18,750 PASS | 2 PASS | `.migration/recon/wave/1/invoices/result.json`, `report.md`, `recon.summary.md` |

Tier 3 was a full diff over every **root** key in both units (25,000 and 18,750 keys are both
under the tolerance record's `full_diff_row_threshold` of 100,000), not a sample. Zero findings
at every tier in both units.

### What the harness verdict does and does not cover (H3)

Tier 3 compares the fields declared in each collection's `fields` list, which are root fields
only; an `embeds` entry carries a cardinality rule, so Tier 1 counts `attributes[]` and
`lines[]` elements against child rows, but no tier compares the child **values**. The wave
verdict above therefore proves root-field equality and embedded-array cardinality, not
embedded-field equality.

That gap is closed by a separate verifier, `scripts/tp_mongo/embed_diff.py`, run in the same
window. It reads every non-orphan child row from the source with the loaders' own predicates
and compares it to the stored array element by identity, parent, order and every declared
field (Decimal128 by value, datetimes in UTC):

| Array | Parents | Children | Fields/child | Value comparisons | Findings |
|---|---|---|---|---|---|
| `invoices.lines` | 18,750 | 149,963 | 19 | 2,849,297 | **0** |
| `customers.attributes` | 25,000 | 8,333 | 4 | 33,332 | **0** |

Evidence: `.migration/recon/wave/embeds/embed_diff.json`. This is supplementary evidence, not
a second merge authority — the harness verdict remains the only one. H3 is filed as harness
feedback (child-field declarations on `EmbedMapping`) in `06_census.md` §7.

## Preconditions checked at the wave boundary

| Precondition | Result |
|---|---|
| Every unit MERGED with a recorded PASS | `customers` #1392 → `83ec971`, `invoices` #1393 → `1743216`, both in `04_progress.md` |
| No collection owned by two units | write-target registry in `04_progress.md`: 5 targets, 5 distinct owners-by-collection, no overlap |
| No unit blocked on an unlanded sibling | `invoices` depends on `customers` only for the customer key, which landed first; nothing was bootstrapped locally |
| Infra check clean at the boundary | the estate has no Terraform for the Atlas target (free-tier M0 created out of band), so the engagement's equivalent gate is `make tp-smoke`: **passed** on this branch |
| Loading quiesced | no loader run during the window; the only writers of `ow_tp_demo{,_quarantine}` are the two unit loaders and neither was invoked |

## Parallel run

STOP B decision **D10** declined CDC/dual-write: the estate is read-only to this engagement,
so there is no sync path to drift. The parallel-run window is therefore what it can honestly
be — repeated hand-triggered `continuous` cycles that would detect either a source-side change
during the window or target-side interference, with Tier 4 replayed once in the window (the
`live` wave recon above).

Each cycle draws its own Tier 3 sample: the runners take `--seed`, and the seed is recorded
next to the verdict in `run_meta.json` so a cycle's sample is reproducible. Cycles run with
the same seed re-inspect the same keys and add no coverage, so the three cycles use seeds
1/2/3 (H4).

| Cycle | Started (UTC) | Seed | `customers` | `invoices` | Drift |
|---|---|---|---|---|---|
| cycle-01 | 2026-09-01T01:59:32Z | 1 | PASS (T1 2 / T2 42 / T3 1,004 sampled) | PASS (T1 2 / T2 9 / T3 1,004 sampled) | 0 |
| cycle-02 | 2026-09-01T01:59:47Z | 2 | PASS (T1 2 / T2 42 / T3 1,003 sampled) | PASS (T1 2 / T2 9 / T3 1,004 sampled) | 0 |
| cycle-03 | 2026-09-01T02:00:02Z | 3 | PASS (T1 2 / T2 42 / T3 1,004 sampled) | PASS (T1 2 / T2 9 / T3 1,004 sampled) | 0 |

Sampling is stratified (first two and last two keys, plus `sample_size` drawn from the seeded
RNG), so the four boundary keys repeat by design and the rest do not: pairwise overlap is
45–49 keys for `customers` and 52–58 for `invoices`, and the three cycles together inspected
2,875 distinct `customers` keys (11.5% of 25,000) and 2,852 distinct `invoices` keys (15.2% of
18,750). Cumulative sampled coverage is what the cycles add over the full-diff wave recon.

Drift count by collection: `ow_tp_demo.customers` 0, `ow_tp_demo.invoices` 0. Time-to-detect
is not measurable against zero drift, and the series is flat rather than monotonic — no
growing gap, which is the signature of a broken sync path. Evidence per cycle:
`.migration/recon/parallel/cycle-0N/{customers,invoices}/{result.json,run_meta.json}`.

The window's value is bounded by D10: it proves the loaded state stays identical to the source
while the source is idle. It does **not** prove a sync path, because there is none, and a
production window with live source writes would need the CDC decision reopened at STOP C.

## Coverage gaps carried forward (unchanged since the census)

| Gap | Status at wave close |
|---|---|
| Postgres `documents` / `document_versions` / `document_snapshots` | not migrated; no source profile for Postgres |
| DynamoDB `otterworks-file-metadata` | not migrated; no source profile for DynamoDB |
| The 16 `OW_BILLING` tables outside the two units | no mapping, no load, no recon coverage |
| `CODES` lookup | out of unit scope; the two Tier 4 replays use the D8 static map |
| 113 all-NULL `CUSTOMER_MASTER` columns | retired (D13); the loader refuses the load if any of them is ever populated |
| `CUST_NAME_UPPER` | still loaded, retired at cutover per the D6 follow-up rather than by a mid-wave mapping change |
| Namespace generality | mapping `1.0.0` hard-codes the `demo` batch in its predicates; a second namespace needs a mapping version bump, not a runner flag |
| Load throughput at production scale | still unmeasured (G4); the measured load is the `demo` namespace only |
| Embedded child fields in the harness verdict | H3: covered by `embed_diff.py` evidence, not by any recon tier; a future mapping version needs child-field declarations before the harness can grade them |
| Sampled Tier 3 coverage in the cycles | each cycle inspects ~1,004 of the unit's keys; the full-key guarantee comes from the `live` wave recon, not from the cycles |

## Cutover readiness

Both units are merged, the wave rollup is green, and parallel-run drift is stable at zero, so
the wave is **eligible** for `!mongo_cutover`. Declaring readiness is not authorizing cutover:
the repoint needs the customer-held cutover principal and a human to start playbook 5.
