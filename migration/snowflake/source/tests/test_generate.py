from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from source.generate import generate


def _digests(folder: Path) -> dict[str, str]:
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(folder.glob("*.csv"))
    }


def test_generation_is_repeatable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UBW_SEED", "20261012")
    first = tmp_path / "first"
    second = tmp_path / "second"

    generate(first)
    generate(second)

    assert _digests(first) == _digests(second)
    assert len(_digests(first)) == 17
