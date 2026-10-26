"""The export validates as SARIF 2.1.0, carries the CarrierSAST stamp, and the
custom rules fire on a fixture tree. Runs offline (--no-registry)."""

import json
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import carrier_sast_export as cse

# Fixture sources are kept as strings so the repository's own scanners do not
# report them as findings.
FIXTURES = {
    "svc-a/src/main/java/demo/ClaimFiles.java": """
package demo;

import java.io.File;
import java.sql.Statement;
import javax.xml.parsers.DocumentBuilderFactory;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;

public class ClaimFiles {
    private static final Logger log = LoggerFactory.getLogger(ClaimFiles.class);
    private static final String DB_PASSWORD = "fixture-only";

    @GetMapping("/claims/doc")
    public File doc(@RequestParam String claimNumber) {
        log.info("fetching document for {}", claimNumber);
        return new File("/srv/claims/" + claimNumber + ".pdf");
    }

    public void find(Statement stmt, String policyNo) throws Exception {
        stmt.executeQuery("SELECT * FROM policies WHERE policy_no = '" + policyNo + "'");
    }

    public Object parser() throws Exception {
        DocumentBuilderFactory f = DocumentBuilderFactory.newInstance();
        return f.newDocumentBuilder();
    }

    public Object safeParser() throws Exception {
        DocumentBuilderFactory f = DocumentBuilderFactory.newInstance();
        f.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
        return f.newDocumentBuilder();
    }
}
""",
    "svc-a/src/main/java/demo/Routes.java": """
package demo;

import org.apache.camel.builder.RouteBuilder;

public class Routes extends RouteBuilder {
    @Override
    public void configure() {
        from("direct:fnol")
            .log("received ${header.ClaimNumber}")
            .to("file:/data/out?fileName=${header.ClaimNumber}.xml");
    }
}
""",
    "svc-a/src/main/resources/application.yml": "spring:\n  datasource:\n    password: ${DB_PASSWORD:fixture-only}\n",
    "svc-a/src/main/resources/maps/lookup.xslt": (
        '<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">\n'
        '  <xsl:param name="ref"/>\n'
        '  <xsl:template match="/"><xsl:copy-of select="document($ref)"/></xsl:template>\n'
        "</xsl:stylesheet>\n"
    ),
    "svc-a/src/main/resources/sample.xml": (
        '<?xml version="1.0"?>\n<!DOCTYPE r [ <!ENTITY ext SYSTEM "file:///etc/hostname"> ]>\n<r>&ext;</r>\n'
    ),
    "svc-a/src/test/java/demo/IgnoredTest.java": (
        'package demo;\nclass IgnoredTest { String password = "fixture-only"; }\n'
    ),
    "svc-b/run.sh": "#!/bin/sh\nexec java -jar $APP_JAR\n",
    "outside/Other.java": 'class Other { String password = "fixture-only"; }\n',
}

EXPECTED_RULES = {
    "carrier.hardcoded-credential",
    "carrier.hardcoded-credential-config",
    "carrier.sql-string-concat",
    "carrier.xxe-parser",
    "carrier.xml-external-entity",
    "carrier.xslt-external-resource",
    "carrier.path-traversal-request-input",
    "carrier.path-traversal-camel-file-uri",
    "carrier.log-policy-claim-identifier",
}


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture(scope="module")
def export(tmp_path_factory):
    repo = tmp_path_factory.mktemp("repo")
    git(repo, "init", "-q")
    for rel, text in FIXTURES.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    git(repo, "add", "-A")
    git(
        repo,
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@example.invalid",
        "commit",
        "-qm",
        "fixture",
    )
    commit = git(repo, "rev-parse", "HEAD")
    paths_file = repo.parent / "paths.txt"
    paths_file.write_text("# scanned\nsvc-a/\n./svc-b\n")
    out = repo.parent / "export.sarif"
    rc = cse.main(
        [
            "--repo",
            str(repo),
            "--commit",
            commit,
            "--paths-file",
            str(paths_file),
            "--run-id",
            "CSAST-TEST-0001",
            "--repository-uri",
            "https://example.invalid/carrier/repo",
            "--no-registry",
            "-o",
            str(out),
        ]
    )
    assert rc == 0
    return commit, json.loads(out.read_text())


def test_validates_against_sarif_2_1_0(export):
    _, sarif = export
    schema = json.loads(cse.SARIF_SCHEMA.read_text())
    jsonschema.Draft4Validator(schema).validate(sarif)
    assert sarif["version"] == "2.1.0"
    assert len(sarif["runs"]) == 1


def test_carries_the_stamp(export):
    commit, sarif = export
    run = sarif["runs"][0]
    assert run["tool"]["driver"]["name"] == "CarrierSAST"
    assert run["automationDetails"]["id"] == "CarrierSAST/CSAST-TEST-0001"
    vcp = run["versionControlProvenance"][0]
    assert vcp["revisionId"] == commit
    assert vcp["repositoryUri"] == "https://example.invalid/carrier/repo"
    stamp = run["properties"]["carrierSast"]
    assert stamp["runId"] == "CSAST-TEST-0001"
    assert stamp["commit"] == commit
    assert stamp["scannedPaths"] == ["svc-a", "svc-b"]
    driver = run["tool"]["driver"]
    assert (
        "semgrep"
        not in json.dumps({k: v for k, v in driver.items() if k != "rules"}).lower()
    )
    for rule in driver["rules"]:
        assert rule["shortDescription"]["text"] == f"CarrierSAST rule {rule['id']}"
        assert "carrier-sast-" not in json.dumps(
            rule
        )  # no temp-dir prefix leaks into rule ids
    for res in run["results"]:
        assert len(res["partialFingerprints"]["carrierSast/v1"]) == 32


def test_custom_rules_fire_and_scope_holds(export):
    _, sarif = export
    results = sarif["runs"][0]["results"]
    fired = {r["ruleId"] for r in results}
    assert EXPECTED_RULES <= fired, EXPECTED_RULES - fired
    uris = {
        loc["physicalLocation"]["artifactLocation"]["uri"]
        for r in results
        for loc in r["locations"]
    }
    assert all(u.startswith(("svc-a/", "svc-b/")) for u in uris), uris
    assert not any("/src/test/" in u for u in uris)
    xxe_lines = [
        r["locations"][0]["physicalLocation"]["region"]["startLine"]
        for r in results
        if r["ruleId"] == "carrier.xxe-parser"
    ]
    assert len(xxe_lines) == 1  # the hardened factory is not reported
    for r in results:
        assert r["level"] in cse.LEVELS
        assert (
            r["locations"][0]["physicalLocation"]["artifactLocation"]["uriBaseId"]
            == "SRCROOT"
        )


def test_summary_counts_match_results(export):
    _, sarif = export
    summary = cse.summarize(sarif)
    assert summary["total"] == len(sarif["runs"][0]["results"])
    assert sum(summary["byLevel"].values()) == summary["total"]
    assert sum(row["count"] for row in summary["byRule"]) == summary["total"]


def test_rejects_paths_outside_the_repository():
    with pytest.raises(SystemExit):
        cse.read_paths(["../etc"], None)
    with pytest.raises(SystemExit):
        cse.read_paths(["/etc"], None)
