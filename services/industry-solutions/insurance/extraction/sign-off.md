# Owner sign-off — unresolved amber decisions

12 decisions below cover all amber rows. Nothing is approved by extraction or by a passing characterization test. Keep the PL/SQL unchanged until an owner chooses the target behavior and separately authorizes a change.

| Decision | Rules | Owner decision needed | Owner / choice / date |
|---|---|---|---|
| D1 | CP-018, CP-045 | Approve T2 at exactly 50000 and align reporting, or choose another shared boundary. OLTP matches the scan; DW labels T1. | Pending / — / — |
| D2 | CP-019, CP-046 | Choose immutable issue premium/tier or approve current-premium repricing; decide how historical recalculation should work. | Pending / — / — |
| D3 | CP-021 | Choose inclusive activation from the scan or approve strictly-after-date legacy behavior, including the initial-date no-rate error. | Pending / — / — |
| D4 | CP-031, CP-061, CP-065 | Decide allocation/recalculation order and whether all write paths must enforce the cap. Current insert-only cap leaves underpayments after repricing and permits over-cap updates; concurrent sessions are not serialized (not load-tested). INSERT SELECT also fails with -4091; choose whether bulk writes must be supported (CP-065). | Pending / — / — |
| D5 | CP-033 | Choose the spec’s 100%/50%/0% bands or legacy 100% before 12 elapsed months, then define policy-month numbering and the anniversary boundary. | Pending / — / — |
| D6 | CP-035 | Define chronology, paid-as-of cutoff, and processing-date versus effective-date booking; legacy accepts pre-issue dates and includes future-period ledger amounts. | Pending / — / — |
| D7 | CP-036 | Define surrender representation and whether it must share lapse chargeback behavior. Do not assume CANCELLED means surrendered. | Pending / — / — |
| D8 | CP-047, CP-049, CP-063 | Decide whether warehouse is a paid-event archive or a current-ledger mirror; MERGE-only loads retain removed rows. The paired CP-048/049 tests demonstrate the divergence. Also decide how corrected product keys propagate: an existing fact keeps its original product attribution (CP-063). | Pending / — / — |
| D9 | CP-053 | Confirm career-agency scope and that upstream annual_premium represents planned annualized premium and FIA single premium. The fixture has no channel field or ingestion mapping to prove those assumptions. | Pending / — / — |
| D10 | CP-059 | Confirm whether the first-year rate may be paid beyond the first year, or provide renewal eligibility/rates. Code has no duration cutoff; the scan is incomplete for later years. | Pending / — / — |
| D11 | CP-060 | Choose allowed input precision and whether totals must be validated after cent-percentage rounding. Legacy accepts exact input totals that round to a stored total above 100%. | Pending / — / — |
| D12 | CP-064 | Decide whether arbitrary rate history must be supported. The conditional unique index also restricts closed history, preventing a second historical closure. Do not weaken or replace it without approval. | Pending / — / — |

## Full catalog approval

After resolving amber items, record approval or rejection of every catalog rule (including green code-only behaviors).

Business owner: __________  Date: __________  Catalog/source fingerprint: __________

Decisions do not authorize a code change in this PR.
