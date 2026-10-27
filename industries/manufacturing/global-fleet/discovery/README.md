# Legacy fleet discovery

Static analysis of the two legacy company-car applications, published as ordered,
indent-2 JSON for a future web reader. No application code is changed.

- `index.json`: app scope and exclusion reasons, file manifest, per-app counts and
  provenance (workflow run, two check rounds, round-2 changes and publication repairs).
- `inventory/<app-id>.json`: app metadata, whole-file `sources_read`, `screens`
  (fields/actions), `records`, `relationships`, `batch_steps`, `unreached` and
  `open_questions` arrays. A singular `source` is a reference string or an array
  when multiple references are needed; `sources` is always an array.
- `rules/<app-id>.json`: `app_id`, `rules` and `navigation_questions`. Rules have
  unique IDs, statements, categories, source references, literal `evidence`, status
  and notes. Navigation questions connect data navigation to business meaning.
- `crosscheck.json`: round-2 rule pairs, shared data, callers and surprises;
  `applied_corrections` records the applied remaining portal fixes (including
  JP-R32). `history` preserves round 1, with references normalized; its corrections
  describe that historical check, not outstanding publication work.

References are repository-relative
`industries/manufacturing/global-fleet/<path>:<start>[-<end>]`, with inclusive,
one-based line numbers. Whole-file/directory lists such as `sources_read` and
`entry_points` omit line numbers. Evidence is a literal source quotation after
whitespace normalization; `...` separates ordered elided fragments, all within
at least one cited range. Explanations of absent checks belong in statements/notes,
not in literal evidence. Detailed evidence repairs are in
`index.json` → `provenance.publication_corrections`.

From the repository root, run (Python standard library only):

```sh
python3 industries/manufacturing/global-fleet/discovery/validate.py
```

The validator reads every JSON file here, checks canonical references and source
bounds, source presence and unique IDs for rules/questions, rule evidence and
crosscheck rule IDs (including history), and coverage of every defined rule in the
final `rule_pairs` (history and prose do not count). Generated
`test-results.json` source labels are test layers rather than citations. It lists
all detected problems and exits 1 on failure, or prints a summary and exits 0.

Run the validator regression tests from the repository root:

```sh
python3 -m unittest discover -s industries/manufacturing/global-fleet/discovery -p 'test_*.py'
```

## Rule catalog

`catalog.json` is the merged rule catalog for the global-fleet app; the admin page
will read it later to show the rules, owner decisions and expected changes. `verdict`
describes whether the legacy apps agree, differ or have a one-sided rule.
`decision.status` is `not-required` for agreements and `decided` otherwise;
`option` records the selected option, `decision` explains it, `open_items` lists
remaining questions, and `linked_to` connects related catalog rules.
`expected_changes` lists anticipated implementation changes. `profiles` holds
the country-specific values and rounding modes used by the app.

Check the catalog from the repository root with the standard-library checker:

```sh
python3 industries/manufacturing/global-fleet/discovery/check_catalog.py
```
