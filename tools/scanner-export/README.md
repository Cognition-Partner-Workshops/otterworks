# CarrierSAST export generator

Runs Semgrep over a list of repository paths at one commit and writes a
SARIF 2.1.0 log stamped as a run of the carrier's scanner, **CarrierSAST**:

| SARIF field | Value |
|---|---|
| `runs[0].tool.driver.name` | `CarrierSAST` (version `1.0.0`) |
| `runs[0].automationDetails.id` | `CarrierSAST/<run id>`; `guid` is derived from run id + commit |
| `runs[0].versionControlProvenance[0]` | `repositoryUri` and `revisionId` (the full commit SHA scanned) |
| `runs[0].properties.carrierSast` | `runId`, `commit`, `scannedPaths`, `excludedPaths`, `rulesets` |
| `results[].partialFingerprints["carrierSast/v1"]` | hash of rule id, file and matched text, for triage across runs |

The default run id is `CSAST-<UTC timestamp>-<12-char commit>`; pass
`--run-id` to set it. Result URIs are repository-relative under the
`SRCROOT` base id.

The scanned tree is extracted from the commit with `git archive`, so the working
tree, uncommitted changes and the checked-out branch do not affect the result.
The generator validates the export against the vendored OASIS schema
(`schema/sarif-schema-2.1.0.json`) before it writes the file.

## Rules

Registry rulesets (fetched from the Semgrep registry at run time):

| Language | Ruleset | Note |
|---|---|---|
| Java | `p/java` | |
| XML | `r/java.servlets` | The registry has no XML pack (`p/xml` does not exist, `r/xml` is empty); this carries its only XML-language rules (`web.xml`). XML/XSLT coverage otherwise comes from the custom rules below. |
| Shell | `r/bash` | Covers `mvnw` and other `*.sh`. |

Custom rules, `rules/carrier-custom.yml`:

| Rule id | Level | Checks |
|---|---|---|
| `carrier.hardcoded-credential` | error | Java string literal assigned to a password/secret/token/key name, `setPassword("...")`, `DriverManager.getConnection(.., .., "...")` |
| `carrier.hardcoded-credential-config` | error | YAML / properties / XML credential keys with a literal value, including a `${VAR:literal}` fallback |
| `carrier.sql-string-concat` | error | SQL text (`SELECT .. FROM`, `INSERT INTO`, `WHERE x =`, ...) concatenated or formatted with a non-constant value |
| `carrier.xxe-parser` | error | `DocumentBuilderFactory`, `SAXParserFactory`, `XMLInputFactory`, `TransformerFactory`, `SchemaFactory`, ... created without `disallow-doctype-decl`, `ACCESS_EXTERNAL_DTD=""` or `SUPPORT_DTD=false` |
| `carrier.xml-external-entity` | error | XML/XSD/XSLT documents that declare an external entity or external DTD |
| `carrier.xslt-external-resource` | warning | XSLT `document()`, `doc()`, `unparsed-text()` on a run-time URI |
| `carrier.path-traversal-request-input` | error | Taint: Spring/JAX-RS request parameters, `HttpServletRequest`, upload file names, Camel message headers/body flowing into `File`, `Path`, `Files.*` |
| `carrier.path-traversal-camel-file-uri` | error | Camel `file:`/`ftp:`/`sftp:` endpoint whose `fileName` comes from `${header.*}`, `${exchangeProperty.*}` or `${body}` |
| `carrier.log-policy-claim-identifier` | warning | Logger, `System.out/err`, `MDC.put` and Camel `.log("${header.ClaimNumber}")` calls that write a policy or claim identifier |

Out of scope by design (`.semgrepignore` written into the extracted tree):
`**/target/`, `**/build/`, `**/node_modules/`, `**/.mvn/`, `**/src/test/`,
`**/*.min.js`. The list is recorded in the export as `excludedPaths`.

## Install

Needs git, Python 3.12 and [uv](https://docs.astral.sh/uv/). From the
repository root:

```bash
cd tools/scanner-export
uv sync
```

`uv.lock` pins Semgrep 1.180.0 and the rest of the environment;
`exclude-newer = "7 days"` keeps resolution off releases younger than a week.

## Run over a path list

A path list is one repository-relative path per line; `#` starts a comment.

```bash
cd tools/scanner-export
cat > /tmp/carrier-paths.txt <<'PATHS'
industries/insurance/claims-hub-camel/
services/commission-service/
PATHS

uv run python carrier_sast_export.py \
  --repo ../.. \
  --commit 4ac447cde0de18e44fc9f5906b719b95013d5c33 \
  --paths-file /tmp/carrier-paths.txt \
  --output /tmp/carrier-sast-export.sarif \
  --summary-json /tmp/carrier-sast-summary.json
```

Paths can also be given as arguments instead of `--paths-file`. The commit must
be present locally (`git fetch origin <branch>` first). Counts by rule and by
level go to stdout and, with `--summary-json`, to a JSON file. `--no-registry`
runs the custom rules only and needs no network.

## Regenerate

Same commit, same paths and the same run id give the same findings, ids, guid
and fingerprints; only the invocation timestamps change. To regenerate an
export, read its stamp and pass it back:

```bash
cd tools/scanner-export
OLD=/tmp/carrier-sast-export.sarif
RUN_ID=$(jq -r '.runs[0].properties.carrierSast.runId' "$OLD")
COMMIT=$(jq -r '.runs[0].properties.carrierSast.commit' "$OLD")
jq -r '.runs[0].properties.carrierSast.scannedPaths[]' "$OLD" > /tmp/carrier-paths.txt

uv run python carrier_sast_export.py --repo ../.. --commit "$COMMIT" \
  --paths-file /tmp/carrier-paths.txt --run-id "$RUN_ID" \
  --output /tmp/carrier-sast-export.regenerated.sarif
```

Registry rulesets are fetched live, so a regenerated export can differ if the
registry changed the rules in between.

## Test

```bash
cd tools/scanner-export
uv run pytest -q
```

The test builds a throwaway git repository with fixture sources, runs the
generator with `--no-registry`, validates the SARIF against the 2.1.0 schema,
checks the stamp (tool name, run id, commit, paths), and checks every custom
rule fires and test sources stay out of scope.

Export files (`*.sarif`) are git-ignored here; they are evidence, not source.
