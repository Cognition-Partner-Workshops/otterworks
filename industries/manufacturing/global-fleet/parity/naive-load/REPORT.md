# What a naive relational migration breaks

What we did: a straight migration of the IDMS unload into PostgreSQL 16. There is one table per record type, the CALC key is the primary key, member foreign keys point at the owner's CALC key, there are no dbkey columns, and `00000000` dates load as NULL. The schema is in `naive_schema.sql` and the loader in `load_naive.py`. The JSF seed goes into a second schema (`jsf_seed`), and the two are merged into `global_merge.global_employee` on `employee_no`. The raw counts and rejected rows are in `results.json`. The "silent" figures below come from `decode.py` over `mainframe/unload` and queries against the loaded DB.

Breaks fall into two kinds. **Loud** ones are rows the database rejects. **Silent** ones are rows that load but now mean something different. The silent ones are the dangerous kind.

| # | What breaks | Kind | Evidence |
|---|---|---|---|
| 1 | The employee CALC key is not unique: `CALC DUPLICATES ARE LAST`. E1010398 (Mia Khan) and E1010524 (Amelia Wright) each have a leaver record (T) and a rehire record (A). | loud | 2 rows rejected on `employee_pkey`. The rehire (A) rows are the ones dropped, because the T rows come first in the file. |
| 2 | Members re-attach to the wrong person once dbkeys are gone. The rehires' 4 assignments and 31 mileage claims carry the rehire dbkeys, but a CALC-key FK attaches them to the surviving **leaver** row. | silent | The naive "current car" query shows LB70 BYG and LN72 SJH against status-T employees. In FLEBEN01 these belong to the active rehires. |
| 3 | More than one open assignment per employee. IDMS allows it: the `EMP-ASSIGN` set is sorted by start date DESC, and FLEBEN01 takes the first one. | loud + silent | 20 rows rejected on `one_open_assignment_per_employee`. In **all 20** cases the row rejected is the *newer* replacement car (file order is start ASC), so the naive table keeps the car the batch does not bill. |
| 4 | Open assignments of leavers. FLEBEN01 caps days at `EM-LEAV`, but SQL `end_date IS NULL` means "still has the car". | silent | 11 of the 81 naive "current car" rows belong to employees with a leave date. |
| 5 | Mileage claims have no vehicle (`MU-VEHID` is spaces = own car). The naive `NOT NULL` FK to vehicle rejects them. | loud | 868 of 1,511 claims (57%) rejected. For 202609 the naive approved mileage is 11,280 mi / 5,019.67 GBP, against 34,306 mi / 15,266.40 GBP in `HP-202609` BENOUT. |
| 6 | Set order is lost. IDMS sets carry an order (`EMP-ASSIGN` by start DESC, `EMP-CLAIM` by date, the report walks in area-sweep/dbkey order). SQL has no order without `ORDER BY`. | silent | BENRPT rows are in dbkey order. Ordering any other way breaks byte parity with the holdouts. The reference port (`../mainframe/reference/fleben01.py`) only matches 12/12 because it walks file order. |
| 7 | Arithmetic semantics. `TAXB` is truncated, because the COMPUTE has no ROUNDED. Each claim is rounded half-up and then summed. Implied decimals: BPCT `1200` = 12.00%, MRATE `0445` = 0.445. A naive `round()` or a decimal-scale slip changes the pence. | silent | Byte-identical 12/12 only with truncation on TAXB plus per-claim ROUND_HALF_UP. |
| 8 | The employee number is not a global identity. The 15 mainframe employees with status X ("transferred abroad") are the same people who appear in the JSF seed under the **same** `E1009xxx` number (E1009100 Priya Raman ... E1009142 Zofia Kowalska). | loud + silent | 15 JSF rows rejected on `global_employee_pkey`, so these people lose their *current* German record and keep their old UK one. |
| 9 | Currency and unit mixing. A single `amount` column holds GBP (UK contribution) and EUR (DE mileage). Distances are miles in one country and km in the other. Nothing in the row says which is which. | silent | `globalEmployeeMerge.amountMapping` in `results.json`. No constraint fails. |
| 10 | Different benefit models. UK: list price × BPCT/12 − contribution, pro-rated by days. DE: 1% of list price + 0.03% × commute km (from `fleet_rule`). They don't fit into one formula column without a country profile. | design | The JSF `FleetService`/`StatementBean` versus FLEBEN01 `2100-BENEFIT`. |
| 11 | Code values. Employee status A/X/T (UK) and the JSF status codes, assignment reason NC/RP/PL, and claim status A/P/R all load as bare `CHAR`, with no shared vocabulary. | silent | Counts in `../../ESTATE.md` and the unload. |

Row totals: the IDMS unload loaded 1,090 rows and had 890 rejected (2 + 20 + 868). The JSF seed loaded cleanly (215/120/111/82/31/699). The global merge's count of 415 people happens to be right (215 IDMS + 200 JSF-only), but it is right for the wrong reasons: the 15 transferred people keep their stale UK row (status X), and the two rehires are represented by their leaver rows.

What the target needs instead:
- A surrogate person id, keeping the legacy dbkey as a provenance column.
- Assignment history with explicit "current" selection rules: latest start ≤ period end, capped by the leave date.
- A nullable vehicle on claims.
- A country profile carrying the currency, the distance unit and the benefit formula.
- Explicit rounding rules per field, each pinned by the holdout pairs.
