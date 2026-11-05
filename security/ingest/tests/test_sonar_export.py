import json
import pathlib
import sys
from io import BytesIO
from unittest.mock import patch

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import sonar_export as se  # noqa: E402

REPO = HERE.parents[2]
NOISE = json.loads((HERE.parent / "fixtures" / "inert-noise.json").read_text())["rows"]


def test_normalise_strips_project_prefix():
    row = se.normalise({"key": "k", "component": "otterworks:a/b.py", "line": 3}, "otterworks")
    assert row["component"] == "a/b.py" and row["tags"] == []


def test_merge_keeps_export_shape_and_drops_seed_labels():
    merged = se.merge_noise([{"key": "real"}], NOISE)
    assert len(merged) == 1 + len(NOISE)
    assert all(set(r) <= set(se.FIELDS) for r in merged[1:])


def test_merge_rejects_key_collision():
    with pytest.raises(ValueError):
        se.merge_noise([{"key": NOISE[0]["key"]}], NOISE[:1])


@pytest.mark.parametrize("row", NOISE, ids=[r["key"] for r in NOISE])
def test_noise_points_at_existing_lines(row):
    path = REPO / row["component"]
    assert path.is_file(), row["component"]
    assert len(path.read_text().splitlines()) >= row["line"]


def test_noise_covers_every_triage_outcome():
    assert {r["seeded_as"] for r in NOISE} == {"duplicate", "false_positive", "unreachable"}


@pytest.mark.parametrize("host", [
    "http://scanner.example.com:9000",
    "http://localhost.example.com",
    "http://localhost@scanner.example.com",
    "http://127.0.0.1.example.com",
])
def test_fetch_refuses_remote_http_before_network_access(host):
    with patch.object(se.urllib.request, "urlopen") as urlopen:
        with pytest.raises(ValueError, match="requires HTTPS for remote hosts"):
            se.fetch(host, "mock", "otterworks")
        urlopen.assert_not_called()


@pytest.mark.parametrize("host", ["", "file:///etc/passwd", "http:///missing-host"])
def test_fetch_refuses_invalid_host(host):
    with patch.object(se.urllib.request, "urlopen") as urlopen:
        with pytest.raises(ValueError, match="must be http or https"):
            se.fetch(host, "mock", "otterworks")
        urlopen.assert_not_called()


@pytest.mark.parametrize("host", [
    "https://scanner.example.com",
    "http://localhost:9000",
    "http://127.0.0.1:9000",
    "http://sonarqube:9000",
])
def test_fetch_allows_https_and_local_http(host):
    with patch.object(se.urllib.request, "urlopen", return_value=BytesIO(b'{"issues": [], "total": 0}')) as urlopen:
        assert se.fetch(host, "mock", "otterworks") == []
        assert urlopen.call_args.args[0].full_url.startswith(host + "/api/issues/search?")


def test_compose_scanner_scope():
    compose = (HERE.parent / "docker-compose.sonarqube.yml").read_text()
    assert "-Dsonar.sources=infrastructure/helm,infrastructure/terraform,platform,services/document-service\n" in compose
    assert "-Dsonar.tests=\n" in compose
    assert "-Dsonar.test.inclusions=\n" in compose
    exclusions = next(line for line in compose.splitlines() if "-Dsonar.exclusions=" in line)
    for pattern in ("**/*.lock", "**/tests/**", "**/.terraform/**"):
        assert pattern in exclusions
