# After-tenant nightly parity

`nightly.py` reruns the committed parity corpus against the deployed after tenant
(`https://t-gf-after.demo.otterworks.app` by default) and reports only the verdicts that changed
since `state.json`.

- **Holdout pairs**: `check_pairs.py` with the reference port proves the corpus still holds
  (`holdout/corpus-and-reference-port`). Then, per pair, the after tenant's
  `GET /api/uk/v1/benefit/periods/{period}/results` is compared with the pair's `BENOUT.dat`
  taxable benefit per employee: `agree`, `differ` (counts of missing, extra, different employees),
  `no-after-result` (the period has no results on the after tenant) or `error`.
  There is no read-only benefit calculation for a closed period (the inquiry and statement return
  the stored run result or an error), so a closed period without results stays `no-after-result`.
- **JSF cases as REST**: `rest_cases.json` maps each of the 40 JSF replay cases, in corpus order, to
  read-only GETs on the after tenant's DE API (`/api/de/v1`) with the business facts the recorded
  portal showed. Each case is `agree`, `differ` (the failed expectations are in the detail) or
  `not-run`: write cases, cases that read state a write created, and UI-only page states are never
  sent, so the harness writes nothing to the tenant. Per-call evidence is in `rest_replay.json`.

Verdicts are raw comparisons: catalog-approved expected changes (e.g. GF29 overlapping assignments)
still show as `differ` here and are judged against the catalog, not hidden.

```sh
python3 parity/after/nightly.py --out /path/to/run            # report only
python3 parity/after/nightly.py --out /path/to/run --write-state  # report and record the new state
```

The run directory holds `CHANGES.md`, `changes.json`, `check_pairs.log` and `rest_replay.json`. The nightly automation commits the updated `state.json` to the
`gf-after-nightly` branch only.
