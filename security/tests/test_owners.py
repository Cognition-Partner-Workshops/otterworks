from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from owners import load, missing  # noqa: E402


def test_load() -> None:
    owners = load()
    assert isinstance(owners, dict)
    assert owners["document-service"] == {
        "team": "Docs Platform",
        "contact": "docs-platform@otterworks.example",
        "escalation": "Page docs on-call for document access incidents.",
    }
    for entry in owners.values():
        assert set(entry) == {"team", "contact", "escalation"}
        assert all(isinstance(value, str) and value for value in entry.values())


def test_load_custom_path(tmp_path: Path) -> None:
    path = tmp_path / "owners.yaml"
    path.write_text("services:\n  frontend-x-fake:\n    team: Web Platform\n")
    assert load(path) == {"frontend-x-fake": {"team": "Web Platform"}}


@pytest.mark.parametrize("content", ["", "services: {}\n", "services:\n"])
def test_load_empty(tmp_path: Path, content: str) -> None:
    path = tmp_path / "owners.yaml"
    path.write_text(content)
    assert load(path) == {}


def test_load_absent_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load(tmp_path / "absent.yaml")


def test_load_invalid_yaml(tmp_path: Path) -> None:
    path = tmp_path / "owners.yaml"
    path.write_text("services: [\n")
    with pytest.raises(yaml.YAMLError):
        load(path)


def test_missing() -> None:
    assert missing(["frontend-z-fake", "document-service", "frontend-x-fake"]) == [
        "frontend-x-fake",
        "frontend-z-fake",
    ]


def test_missing_empty() -> None:
    assert missing([]) == []
    assert missing(["document-service"]) == []
