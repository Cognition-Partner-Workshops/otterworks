import json
import pathlib
import sys

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
