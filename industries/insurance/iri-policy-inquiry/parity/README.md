# Frozen parity and schema checks

The capture owner runs `python3 parity/capture.py iri` against their running legacy
API. Never overwrite frozen records to make a comparison pass. Each JSON record
retains operation, contract, request, HTTP status, raw SHA256 and decoded body;
manifest.json describes the complete capture.

Install Python dependencies with `pip3 install --user pyyaml jsonschema`.
From the inquiry directory:

- `python3 lineage/render.py --check`
- `python3 parity/compare.py --op summary --ns iri`
- `python3 parity/compare.py --op values --dry-run`
- `python3 parity/schema_check.py --op funds --ns iri`
- `python3 -m unittest discover -s parity -p 'test_*.py'`

Both live checks require an implemented operation and running IRI API.
Reports are written to parity/reports/<op>-parity.{json,md} and
<op>-schema.{json,md}. Dry-run has a separate <op>-dry-run report and makes
**no parity claim**. It validates legacy formatting, applies all sourced transforms,
and reports sign-off/not-in-operation/omitted-optional separately (never as passes).
Required children of deliberately omitted optional parents stay in the lineage
inventory as omitted-optional, not business sign-offs. Segment child requirements
are grouped under the single FUND_UNITS segment business decision.
No frozen records is an error, not a vacuous success.

All transformation definitions and field mappings come from lineage/lineage.yaml.
Repeated _NN rows represent every two-digit suffix, validated against FUND_CNT;
fund order is the legacy repository's ORDER BY fund_code. Live funds comparisons
support --start-index and --limit (50 default, 200 max), validate array length,
itemsCount and totalItemsCount. Non-success statuses compare RTN_CD via the same
status map; error payload shape is checked separately by schema_check.
The schema check resolves pinned local refs, uses Draft 2020-12 with format
checking, validates every captured contract and requires an extra absent contract
to return 404. Override --not-found if that contract is added to the fixture.

A difference is a failure until explained from data. Business-only decisions
go on the sign-off list and the field stays in the payload. A clean mapped-field
report does not imply completeness while sign-off entries remain.

## Legacy drift replay

With Oracle and the legacy API running, use `make iri-parity-replay NS=iri`
from repo root (NS defaults to iri), or from this directory:

```sh
python3 parity/replay.py --ns iri
python3 parity/replay.py --ns iri --frozen-dir /path/to/baseline-copy --out /path/to/drift-report
```

Replay reuses capture.py's raw HTTP fetcher, re-enumerates contracts, and fetches
all three operations for every live contract. It compares HTTP status, raw body
SHA256 (including serialization/whitespace), and decoded JSON body independently.
It never updates frozen evidence. Added/removed contracts are compared against
manifest.json and counted as drift for each operation. Removed contracts are not
fetched because they no longer appear in the live list.

Default output is parity/reports/drift-<UTC timestamp>.json and .md; `--out`
accepts a report stem or a .json/.md path. Outputs inside either the selected
baseline or the canonical frozen directory are rejected. Reports contain
per-operation checked/unchanged/drifted counts, added/removed contracts and
field-level differences for every drifted record, including status/hash changes.

Exit codes: **0** complete replay with no drift, **1** drift or an invalid legacy
response, **2** legacy transport failure (also normal argparse usage errors).
On a transport failure, the partial report has complete=false and records the
failed URL; it must not be interpreted as a clean replay.
To demonstrate drift safely, copy frozen elsewhere and alter the copy, then use
`--frozen-dir`. Never edit canonical frozen records to test or eliminate drift.
