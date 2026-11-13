import json
import pathlib
import re
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parents[1]
REPO_ROOT = HERE.parents[4]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO_ROOT / "security/ingest"))
import cluster_sarif
import devin_ingestion
import generate_findings as gf


@pytest.fixture(scope="module")
def manifest():
    return gf.load_manifest()


@pytest.fixture(scope="module")
def report():
    return json.loads((HERE / "findings.sarif").read_text())


def test_committed_export_matches_source():
    assert gf.main(["--check"]) == 0


def test_twenty_seven_findings_one_run_per_repository(report, manifest):
    ids = sorted(r["properties"]["findingId"] for run in report["runs"] for r in run["results"])
    assert ids == [f"VSL-{n:02d}" for n in range(1, 28)]
    assert sorted(run["properties"]["repository"] for run in report["runs"]) == sorted(
        project["repository"] for project in manifest["projects"].values())


def test_every_location_resolves_to_its_anchor(report, manifest):
    anchors = {f"VSL-{f['id']:02d}": f["anchor"] for f in manifest["findings"]}
    for run in report["runs"]:
        for result in run["results"]:
            location = result["locations"][0]["physicalLocation"]
            line = (REPO_ROOT / location["artifactLocation"]["uri"]).read_text().splitlines()[
                location["region"]["startLine"] - 1]
            assert re.search(anchors[result["properties"]["findingId"]], line)


def test_checkmarx_fields_present(report):
    for run in report["runs"]:
        rules = {rule["id"]: rule for rule in run["tool"]["driver"]["rules"]}
        for result in run["results"]:
            assert rules[result["ruleId"]]["name"] == result["properties"]["queryName"]
            assert result["properties"]["severity"] in gf.SARIF_LEVEL
            assert result["properties"]["cwe"].startswith("CWE-")
            assert isinstance(result["properties"]["similarityId"], int)


def test_shared_library_ssrf_clusters_with_consumer_ssrf(report):
    ssrf = next(group for group in cluster_sarif.cluster(report) if group["cwes"] == ["CWE-918"])
    assert ssrf["repos"] == ["uc-vuln-shared-lib-dev-api", "uc-vuln-shared-lib-platform-shared"]


def test_ingestion_request_names_all_four_repositories(report):
    body = devin_ingestion.request_body(report, "profile", "https://example.org/findings.sarif")
    assert [repo["repo_name"] for repo in body["repos"]] == [
        "uc-vuln-shared-lib-android-app", "uc-vuln-shared-lib-dealer-portal",
        "uc-vuln-shared-lib-dev-api", "uc-vuln-shared-lib-platform-shared"]


def test_csv_exports_cover_every_finding():
    findings = (HERE / "findings.csv").read_text().splitlines()
    prioritized = (HERE / "prioritized.csv").read_text().splitlines()
    assert findings[0].startswith("SimilarityID,FindingID,Query,Severity")
    assert prioritized[0] == "asset,finding_id,finding,severity,risk_score,sla_due,owner_team,location"
    assert len(findings) == len(prioritized) == 28


def test_anchor_must_match_exactly_once(tmp_path):
    (tmp_path / "a.cs").write_text("x\nx\n")
    with pytest.raises(ValueError, match="matched 2 lines"):
        gf.locate({"id": 1, "path": "a.cs", "anchor": "x"}, tmp_path)
