# 01_conventions

## Namespaces
- Target database: `ow_billing_offline` (the only entry in `allowed_targets.json`). Nothing writes anywhere else.
- Collection names: snake_case domain nouns from `03_mapping_spec.json`; every unit's write targets are declared in its wave manifest.
- Local fixture Oracle schema: `FIXTURE` inside `FREEPDB1` (compose default). Never the source system.

## Branches and PRs
- Working branch: `tp-run/mongodb-20260922T142645Z`. Every PR targets it; never `tech-partnerships`, never `main`.
- Unit branch: `migrate/billing/<wave>-<unit>` off the working branch. One PR per unit, no stacking.
- PR body shape, in order, under 2,000 characters:
  1. **Decisions** — the `D-<id>` rows this unit relies on.
  2. **Code** — loader, seed, tests; write targets.
  3. **Evidence** — unverified paths first; `recon.summary.md` rendered inline, raw JSON linked; `merge_eligible: false` stated plainly with the reason (`recon_mode: offline`, fixture only, live recon pending customer run).
- `make tp-smoke` runs before every PR.
- PRs describe the estate as the production legacy system it is.
- Never hand-edit `03_mapping_spec.json`; regenerate with `model_patch.py` from `05_decisions.json`.

## Files under `.migration/`
- `02_tolerances.json`, `03_mapping_spec.json` are the versioned inputs `recon run` loads and cites.
- `05_decisions.json` (machine) and `05_decisions.md` (human) hold every decision with `file:line` or `source: customer` evidence.
- `recon/<unit>/` holds redacted harness output only; verdicts are never edited.
- `waves/wave-<N>.json` manifests carry write targets, `width`, `auto_merge: false`.

## Commands
- Every offline command runs as `env -u MONGODB_ATLAS_URI ...`.
- Harness venv: `/home/ubuntu/mmp-venv` (`recon run`, `recon selftest`).
