# Parity comparisons

The default `comparison: exact` retains unique-key, equal-row comparisons.

`comparison: candidates` is opt-in for outputs whose legacy ordering permits
multiple legal winners. The legacy SQL must supply one row for an unambiguous
key and every legal candidate for an ambiguous key. The lakehouse must supply
exactly one row per key, matching **all** comparison columns of one candidate.
Missing, extra, duplicate lakehouse and null keys fail. Candidate values are
compared exactly after declared normalization; numeric tolerances are rejected.
Selecting candidates is the spec SQL's responsibility, not a heuristic in the
engine. The documents specs retain published legacy rows for untied keys and
expand only latest-timestamp ties from legacy staging.

Optional `candidate_aggregate` checks an aggregate output alongside its selected
contributions. Both readers return contribution rows with repeated observed
aggregate columns. Configure `group_keys`, contribution `value`, observed
`count`, and observed `total`. All candidates for a key must share group keys.
The engine requires one legal contribution per key, recomputes COUNT and SUM
from the matching **legacy** candidates, checks every repeated observed value,
and requires the total to lie within sums of per-key possible minima/maxima.
SUM ignores null contributions and remains null when all selected values are
null. Groups without ambiguous contributions also match the published legacy
count and total exactly. Readers must expose missing/extra aggregate groups;
the documents workspace spec uses a full outer join on the lakehouse side.

Reports and CLI output expose `exact_matched_rows`, `tie_resolved_rows`, and
`mismatches`. Counts refer to output keys, or aggregate groups when configured;
input `row_counts` count candidate/contribution rows, not aggregate outputs.
Any mismatch fails the report. Aggregate reports include a bounded sample of
possible totals and recomputed totals plus the number of groups checked.
