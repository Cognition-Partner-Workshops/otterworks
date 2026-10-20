# claims-hub-dual-run

Nightly dual run of the BizTalk claims hub: the Saxon behaviour corpus in `../biztalk-claims-intake` against every
`../claims-hub-camel` ref in flight, message by message. A Devin automation runs it at 03:00 UTC; anyone can run it by hand.

```bash
# JDK 21 and a reachable Maven repository are the only prerequisites besides Python 3.11+, git, gh and Docker.
JAVA_HOME=/path/to/jdk-21 MVNW_REPOURL=https://maven-central.storage-download.googleapis.com/maven2 \
  python3 industries/insurance/claims-hub-dual-run/dual_run.py          # writes ~/claims-hub-dual-run/out/report.md
python3 industries/insurance/claims-hub-dual-run/dual_run.py --camel-ref origin/devin/<branch>   # one ref only
```

What it does:

1. **Saxon side.** Checks out the fixture (`demo-insurance` once `devin/1792473658-insurance-biztalk-fixture` has merged
   into it, the fixture branch until then) and runs `make deps && make check`, then each of the three check steps on its
   own so a red map step does not hide the positional and triage steps. The committed goldens are the Saxon side: 112 map
   outputs, 14 positional files, 16 triage results.
2. **Camel side.** Every ref that has `claims-hub-camel/pom.xml`: `demo-insurance` if the module has merged, plus every
   open pull request into `demo-insurance` whose diff touches `claims-hub-camel/`. Each is checked out in its own worktree
   with the same fixture copied in, then `./mvnw verify -Dclaims.fixture.dir=… -Dfixture.dir=…` runs its golden tests.
   Two overlays are copied into the worktree only (never committed to those branches):
   - `overlay/DualRunCapture.java`, called from the first line of `ByteComparison.of`, keeps every output a Camel test
     compares with a golden, keyed by the golden's SHA-256 (map goldens, the vendor positional files, anything else
     compared through `ByteComparison`);
   - `overlay/DualRunTriageCaptureTest.java`, where the rules table (`TriageEvaluator`) exists, writes each
     `TriageResult`; the harness lays it out exactly as `tools/triage_reference.py` does (`json.dumps(indent=2)` + `\n`).
   If an overlay stops compiling against a ref, that ref is re-run without it so its tests still report, but the ref is
   marked *capture missing* and the run exits 2: a ref whose outputs were not captured has not been compared.
   Docker Hub pulls are rate-limited on Devin machines, so bare image names the tests use are pulled from `mirror.gcr.io`
   and tagged first. Ryuk is disabled; every container started during a ref's build is removed afterwards and counted,
   also when `./mvnw verify` hits `--maven-timeout` (default 1800 s), which marks the ref as a failed build.
3. **Comparison.** One row per Saxon message: Saxon bytes and hash, Camel bytes and hash, which refs and tests produced
   it, the first differing byte (offset, line/column, both bytes, an excerpt of each side), verdict and cause. The cause
   is the one the Camel test wrote in its own `target/golden-report/*.md` row; for triage it is the differing fields.
   A message no ref produces yet is *not covered*, which is not a difference. Totals are at the bottom.

Output in `--work/out/`: `report.md`, `summary.json`, `logs/` (gate and Maven logs, each ref's golden reports).

Exit status: `0` every captured Camel output is byte-identical and every gate/build ran; `1` at least one byte
difference; `2` no byte difference, but the Saxon gate was red, `./mvnw verify` exited non-zero or timed out on a ref,
a ref's capture overlay was missing or captured nothing, or a Camel test failed (listed under "Red Camel tests").
