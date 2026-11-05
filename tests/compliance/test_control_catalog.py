import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "compliance/control-catalogs/validate_catalog.py"
SPEC = importlib.util.spec_from_file_location("validate_catalog", SCRIPT)
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)
CATALOG = json.loads(validator.DEFAULT_CATALOG.read_text())


def test_catalog_contract():
    assert CATALOG["framework"] == "secure-software-controls"
    assert CATALOG["name"] == "Secure Software Control Standard"
    assert CATALOG["version"] == 1
    criteria = validator.validate_catalog(CATALOG)
    assert [c["id"] for c in criteria] == [f"SSC-{i:02d}" for i in range(1, 13)]
    assert criteria == [
        {"id": c["id"], "text": f'{c["title"]}: {c["text"]}'}
        for c in CATALOG["controls"]
    ]


@pytest.mark.parametrize("field", ["title", "text", "references", "evidence"])
@pytest.mark.parametrize("value", [None, "", "  ", [], [" "], 42])
def test_invalid_required_fields(field, value):
    catalog = copy.deepcopy(CATALOG)
    catalog["controls"][0][field] = value
    with pytest.raises(ValueError, match=field):
        validator.validate_catalog(catalog)


@pytest.mark.parametrize("field", ["title", "text", "references", "evidence", "id"])
def test_missing_required_fields(field):
    catalog = copy.deepcopy(CATALOG)
    del catalog["controls"][0][field]
    with pytest.raises(ValueError):
        validator.validate_catalog(catalog)


@pytest.mark.parametrize("control_id", [None, 1, "", "SSC-1", "SSC-001", "ABC-01", "SSC-01\n"])
def test_invalid_ids(control_id):
    catalog = copy.deepcopy(CATALOG)
    catalog["controls"][0]["id"] = control_id
    with pytest.raises(ValueError, match="id"):
        validator.validate_catalog(catalog)


def test_duplicate_ids():
    catalog = copy.deepcopy(CATALOG)
    catalog["controls"].append(catalog["controls"][0])
    with pytest.raises(ValueError, match="duplicate"):
        validator.validate_catalog(catalog)


@pytest.mark.parametrize("catalog", [None, [], {}, {"controls": []}, {"controls": {}}, {"controls": [None]}])
def test_invalid_catalog_structure(catalog):
    with pytest.raises(ValueError):
        validator.validate_catalog(catalog)


def test_cli_criteria_json():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--criteria-json"],
        cwd=SCRIPT.parent,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout) == validator.validate_catalog(CATALOG)
    assert result.stderr == ""


@pytest.mark.parametrize("content", ["", "{", '{"controls": []}'])
def test_cli_rejects_invalid_catalog(tmp_path, content):
    path = tmp_path / "invalid.yaml"
    path.write_text(content)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert result.stderr.startswith("Invalid catalog:")
    assert result.stdout == ""


def test_cli_missing_file(tmp_path):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path / "missing.yaml")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert result.stderr.startswith("Invalid catalog:")
