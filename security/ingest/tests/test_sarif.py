import copy
import json
import pathlib
import sys
from contextlib import contextmanager
from io import StringIO
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import cluster_sarif as cs
import devin_ingestion as di
import sonar_sarif as ss


@pytest.fixture
def fixture():
    return json.loads((pathlib.Path(__file__).resolve().parents[1] / "fixtures/sonar-project.json").read_text())


def test_export(fixture):
    run = ss.build_run("owner/one", "abc", fixture["rows"], fixture["rules"])
    assert len(run["results"]) == 4
    result = run["results"][0]
    assert result["level"] == "error"
    assert result["properties"]["security-severity"] == "8.0"
    assert result["properties"]["repository"] == "owner/one"
    assert "cwe-89" in result["properties"]["tags"]
    assert result["locations"][0]["physicalLocation"]["region"]["startLine"] == 4
    assert run["tool"]["driver"]["rules"][0]["shortDescription"]["text"] == "Avoid unsafe queries"
    assert "& validation" in run["tool"]["driver"]["rules"][0]["fullDescription"]["text"]
    changed = copy.deepcopy(fixture["rows"])
    changed[0]["key"] = "new-server-generated-id"
    assert ss.build_run("owner/one", "def", changed, fixture["rules"])["results"][0]["partialFingerprints"] == result["partialFingerprints"]
    assert ss.build_run("owner/two", "abc", fixture["rows"], fixture["rules"])["results"][0]["partialFingerprints"] != result["partialFingerprints"]


def test_clusters(fixture):
    report = ss.document([ss.build_run(repo, "abc", fixture["rows"], fixture["rules"]) for repo in ("owner/one", "owner/two")])
    groups = cs.cluster(report)
    shared = next(g for g in groups if g["cwes"] == ["CWE-89"])
    assert shared["count"] == 6
    assert shared["repos"] == ["owner/one", "owner/two"]
    assert "| 6 | owner/one, owner/two |" in cs.markdown(groups)
    assert di.request_body(report, "profile", "https://example.org/file")["repos"] == [
        {"repo_name": "owner/one", "host": "github.com"}, {"repo_name": "owner/two", "host": "github.com"}]


def test_empty_and_invalid():
    report = ss.document([ss.build_run("owner/repo", "abc", [], {})])
    assert cs.cluster(report) == []
    assert len(cs.markdown([]).splitlines()) == 2
    with pytest.raises(ValueError):
        cs.cluster({"version": "1"})
    with pytest.raises(ValueError):
        di.request_body(ss.document([]), "p", "url")
    with pytest.raises(ValueError):
        ss.api("file:///etc/passwd", "token", "issues/search")


def test_collect_hotspots_and_errors(monkeypatch, fixture):
    monkeypatch.setattr(ss, "fetch", lambda *args, **kwargs: fixture["rows"][:1] if kwargs == {"types": "VULNERABILITY", "severities": "CRITICAL"} else [])
    responses = [
        {"hotspots": [{"key": "h", "component": "p:src/A.java", "line": 2}], "paging": {"total": 1}},
        {"rule": {"key": "java:S1", "vulnerabilityProbability": "HIGH"}},
        {"rule": fixture["rules"]["java:S1"]},
    ]
    mock = Mock(side_effect=responses)
    monkeypatch.setattr(ss, "api", mock)
    rows, rules = ss.collect("http://localhost", "token", "p")
    assert mock.call_args_list[0].kwargs["project"] == "p"
    assert rows[-1]["type"] == "SECURITY_HOTSPOT"
    assert rows[-1]["component"] == "src/A.java"
    assert rows[-1]["severity"] == "CRITICAL"
    assert rules["java:S1"]["name"] == "Avoid unsafe queries"
    monkeypatch.setattr(ss, "api", Mock(side_effect=TimeoutError))
    with pytest.raises(TimeoutError):
        ss.collect("http://localhost", "token", "p")


def test_dry_run(tmp_path, capsys, monkeypatch):
    path = tmp_path / "report.sarif"
    path.write_text(json.dumps(ss.document([ss.build_run("owner/repo", "sha", [], {})])))
    monkeypatch.setattr(di.requests, "post", Mock(side_effect=AssertionError("Network forbidden")))
    monkeypatch.setenv("DEVIN_ENTERPRISE_API_KEY", "not-a-real-key")
    assert di.main([str(path), "--org", "org-test", "--profile", "profile-test", "--dry-run"]) == 0
    output = capsys.readouterr().out
    assert "not-a-real-key" not in output
    assert json.loads(output)["ingestion"]["json"]["profile_id"] == "profile-test"


def test_upload_then_ingestion(tmp_path, monkeypatch):
    path = tmp_path / "report.sarif"
    path.write_text(json.dumps(ss.document([ss.build_run("owner/repo", "sha", [], {})])))
    upload = Mock()
    upload.json.return_value = {"url": "https://example.org/attachment"}
    started = Mock()
    started.json.return_value = {"scan_id": "scan-test"}
    post = Mock(side_effect=[upload, started])
    monkeypatch.setattr(di.requests, "post", post)
    monkeypatch.setenv("DEVIN_ENTERPRISE_API_KEY", "not-a-real-key")
    args = [str(path), "--org", "org-test", "--profile", "profile-test"]
    assert di.main(args) == 0
    assert post.call_args_list[0].args[0].endswith("/organizations/org-test/attachments")
    assert post.call_args_list[1].kwargs["json"]["attachment_urls"] == ["https://example.org/attachment"]
    failed = Mock()
    failed.raise_for_status.side_effect = di.requests.HTTPError("upload failed")
    post = Mock(return_value=failed)
    monkeypatch.setattr(di.requests, "post", post)
    with pytest.raises(di.requests.HTTPError):
        di.main(args)
    assert post.call_count == 1


def test_issue_pagination_and_overflow(monkeypatch):
    pages = iter([{"total": 501, "issues": [{"key": "one", "component": "p:a.py"}]},
                  {"total": 501, "issues": [{"key": "two", "component": "p:b.py"}]}])

    @contextmanager
    def urlopen(request, timeout):
        assert "types=BUG" in request.full_url
        yield StringIO(json.dumps(next(pages)))

    monkeypatch.setattr(ss.urllib.request, "urlopen", urlopen)
    assert [row["key"] for row in ss.fetch("http://localhost", "t", "p", types="BUG")] == ["one", "two"]
    pages = iter([{"total": 10001, "issues": []}])
    with pytest.raises(ValueError, match="exceeds 10000"):
        ss.fetch("http://localhost", "t", "p", types="BUG")


def test_cluster_separates_cwe_and_escapes(fixture):
    runs = [ss.build_run("owner/one", "sha", fixture["rows"][:1], fixture["rules"])]
    other = copy.deepcopy(runs[0])
    other["results"][0]["properties"]["tags"] = ["cwe-79"]
    other["tool"]["driver"]["rules"][0]["properties"]["tags"] = []
    other["results"][0]["properties"]["repository"] = "owner/pipe|name"
    groups = cs.cluster(ss.document(runs + [other]))
    assert len(groups) == 2
    assert "pipe\\|name" in cs.markdown(groups)


def test_security_standards_list():
    assert ss.tags_for({}, {"securityStandards": ["cwe:89", "owaspTop10:a1"]}) == ["cwe:89", "owaspTop10:a1"]
