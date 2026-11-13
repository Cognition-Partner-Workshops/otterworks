# Auditor evidence pack

Requires Python 3, PyYAML, Git, `gh` authenticated with alert/PR read access,
curl and tar. No application dependencies are installed. Run from the repo root:

```sh
git fetch origin demo-ciso main
bash compliance/evidence/live_check.sh
python3 compliance/evidence/build_evidence_pack.py --branch demo-ciso \
  --live-dir compliance/evidence/out \
  --out compliance/evidence/evidence-pack.md \
  --json compliance/evidence/evidence-pack.json
# Or: make evidence-pack
python3 -m pytest compliance/evidence/tests
ruff check compliance/evidence
```

The live script pins Trivy 0.71.0 and Gitleaks 8.21.2 under `~/bin`, scans
filesystem dependencies offline (Maven transitive coverage may be incomplete),
final-stage service base images, and redacted full Git history. It records failures
without treating them as clean scans. It can take a while and needs network access
for databases, images and scanner releases. Output, API cache and logs are ignored.
Gitleaks exit 1 means findings, not a scanner failure. Do not commit raw secret scans.

The builder reads source files from `origin/<branch>` at its resolved SHA, validates
the SSC catalog with `validate_catalog.py`, queries paginated GitHub REST data via
`gh api`, and emits Markdown/JSON. `--refresh` bypasses the local API cache. Missing
live data is explicitly “not checked”; reused scans carry their original SHA/time.
Git history must be complete. Do not reuse cached data across audit snapshots
without considering its timestamp. Restricted CodeQL data is a warning, not a clean
bill of health; Dependabot and PR collection errors stop the build.

`control-map.yaml` is a curated mapping for **human sign-off**, not a claim that an
AI has performed a human review. Reason detection uses text heuristics; reviewers
must check the source links and comment blocks. Terraform suppressions are catalog
coverage gaps, not application-control coverage. Workflow analysis is static:
branch/path filters, job conditions and fail-open markers do not establish branch
protection or that a run occurred. Reusable workflows have no direct push/PR trigger.

SLA days (7/30/90/180) are explicitly assumptions, not repository policy; the sprint
guide says critical “immediately” and high “within the current sprint”. Durations are
elapsed UTC days, p90 is nearest rank. Default-branch Dependabot/CodeQL evidence is
separate from target-branch exceptions. Fixing PR attribution uses the last main
commit touching a manifest before `fixed_at` and is labelled heuristic. Merged PRs
mentioning named findings are references, not independently proven fixes. Counts
are evidence records and can overlap. No scanner suppression is changed by this tool.

## Weekly unattended refresh

`make evidence-weekly` (or `bash compliance/evidence/weekly_refresh.sh --branch demo-ciso`)
scans the current HEAD, runs `make deps-inventory` and `make deps-gate`, dispatches
`sonarqube-banking.yml` on the specified remote branch, waits up to 90 minutes and
downloads its clusters artifact. It then rebuilds the pack with `--source-ref HEAD`
and writes `out/weekly-summary.md` (at most 40 lines) plus `weekly-status.json`.
The branch must exist on GitHub and support workflow dispatch. Concurrent ambiguous
dispatches are reported rather than attributed speculatively. Dispatch, scanner and
advisory failures are captured and do not prevent the other evidence steps. Dependency
checks need uv, Maven/Gradle and the JDKs declared in `security/deps/modules.yaml`;
missing tools/JDKs produce inconclusive evidence, not a pass. Commit code before
collecting a weekly snapshot. Generated pack changes will naturally be committed
after the SHA whose sources were scanned; no self-referential SHA is claimed.
