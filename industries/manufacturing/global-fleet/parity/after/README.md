# After-tenant nightly parity

`nightly.py` reruns the committed parity corpus against the deployed after tenant
(`https://t-gf-after.demo.otterworks.app` by default) and reports only the verdicts that changed
since `state.json`.

- **Holdout pairs**: `check_pairs.py` with the reference port proves the corpus still holds
  (`holdout/corpus-and-reference-port`). Then, per pair, the after tenant's
  `GET /api/uk/v1/benefit/periods/{period}/results` is compared with the pair's `BENOUT.dat`
  taxable benefit per employee: `agree`, `differ` (counts of missing, extra, different employees),
  `no-after-result` (the period has no results on the after tenant) or `error`.
- **JSF replay**: `jsf/replay.py --stage full --base <after>`; each of the 40 cases is `agree`
  (identical observation), `differ`, or `not-run` (replay aborted earlier; the reason is in the detail).

Verdicts are raw comparisons: catalog-approved expected changes (e.g. GF29 overlapping assignments)
still show as `differ` here and are judged against the catalog, not hidden.

```sh
python3 parity/after/nightly.py --out /path/to/run            # report only
python3 parity/after/nightly.py --out /path/to/run --write-state  # report and record the new state
```

The run directory holds `CHANGES.md`, `changes.json`, `check_pairs.log`, `replay.log` and the replay
evidence under `jsf/`. The nightly automation commits the updated `state.json` to the
`gf-after-nightly` branch only.
