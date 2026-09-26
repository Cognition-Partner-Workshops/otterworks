# 01 Conventions

## Branches (binding for the orchestrator and every child)
- Run branch: `tp-run/mongodb-20260926T170458Z-rt-fanout`, cut from `origin/tech-partnerships`.
- Every `.migration/` commit and every unit PR targets the run branch. Never merge into `tech-partnerships` or `main`.
- Unit branches: `migrate/<domain>/<wave>-<unit>` cut from the run branch (e.g. `migrate/mmp_rt/w1-users`).
- **Branch isolation rule:** do not read, fetch, check out, diff, or search any other branch or PR of this repo — including `tech-partnerships-solutions` and any closed PR. Only `tech-partnerships` (before-state) and the run branch exist for this engagement. This rule goes verbatim into every child brief.
- Every PR into `tp-run/*` must pass the `tp-golden-smoke` gate (`make tp-smoke` locally).

## Write targets
- Only database `mmp_rt_billing_n` on cluster `otterworks-demo` (`allowed_targets.json`). Never write to `mmp_rt_src` or any other database. No users, roles, or grants are created anywhere.
- Credentials by secret name only: source `MONGODB_MMP_RT_SOURCE_URI`, target `MONGODB_MMP_RT_TARGET_N_URI`. `MONGODB_MMP_RT_TARGET_URI` and `MONGODB_ATLAS_URI` are never used. No credential value in any artifact, log, PR, transcript, or code.
- Children never edit `.migration/`; the fan-out workflow is the single writer of wave results.

## Environment fix (run once per session, including every child)
```
~/.venvs/recon/bin/python -m pip install -U pip setuptools && ~/.venvs/recon/bin/python -m pip install -e "$(ls -d /opt/.devin/plugins/cache/*mongo-migration-plugin*/*/skills/mongo-recon-harness/harness | head -1)[all,test]" && ~/.venvs/recon/bin/recon selftest
```

## Naming
- Target collections keep source names (`users`, `folders`, `documents`, `comments`, `shares`, `audit_events`); quarantine collections are `_quarantine_<collection>`.
- Field names camelCase (org convention). Migration-owned fields carry the `_mig` prefix (e.g. `_migSourceId`) if ever needed.

## PR shape (<2,000 characters)
1. **Decisions** — decision ids from `05_decisions.md` the unit relies on; any ESCALATE.
2. **Code** — files changed, unverified paths listed FIRST.
3. **Evidence** — `recon.summary.md` rendered inline, raw `recon.json` linked under `.migration/recon/<unit>/`; mode, target class, tolerance version.
- Reviewer: none (intake). Merge authority: recon verdict + independent verifier via the fan-out workflow, `auto_merge: true` (soft mode).

## Recon invocation (children)
`~/.venvs/recon/bin/recon run --family mongodb-atlas --mapping .migration/03_mapping_spec.json --tolerances .migration/02_tolerances.json --mode fixture` for development; exactly one `--mode live --target-class migration_cluster` run per unit (source concurrency cap 2, re-run cap 3, then escalate). Harness output is never hand-edited.
