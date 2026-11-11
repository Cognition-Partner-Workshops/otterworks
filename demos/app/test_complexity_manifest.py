import json
import runpy
from pathlib import Path

import pytest

HELPER = runpy.run_path(str(Path(__file__).with_name("complexity_manifest.py")))
load_demo = HELPER["load_demo"]
load_demos = HELPER["load_demos"]


def write(tmp_path, value):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(value))
    return path


@pytest.fixture
def block():
    return {"demo": "first", "spec": "first/spec.md", "classes": [{"id": "A", "planted_keys": ["a"]}]}


def test_v1_and_v2_return_same_reader_shape(tmp_path, block):
    v1 = {"schema_version": 1, **block}
    assert load_demo(write(tmp_path, v1), "first") == v1
    v2 = {"schema_version": 2, "demos": [block, {**block, "demo": "second"}]}
    path = write(tmp_path, v2)
    assert load_demo(path, "first") == v1
    assert list(load_demos(path)) == ["first", "second"]
    assert load_demo(path, "second")["demo"] == "second"
    with pytest.raises(ValueError, match="Unknown"):
        load_demo(path, "absent")


@pytest.mark.parametrize("value", [
    {"schema_version": 3}, {"schema_version": True}, {"schema_version": 2, "demos": []},
    {"schema_version": 2, "demos": [{}]},
    {"schema_version": 2, "demos": [{"demo": "x", "spec": "s", "classes": [{"id": "a"}, {"id": "a"}]}]},
    {"schema_version": 2, "demos": [{"demo": "x", "spec": "s", "classes": [None]}]},
])
def test_invalid_registers(tmp_path, value):
    with pytest.raises(ValueError):
        load_demos(write(tmp_path, value))


def test_duplicate_demo_names(tmp_path, block):
    with pytest.raises(ValueError, match="Duplicate"):
        load_demos(write(tmp_path, {"schema_version": 2, "demos": [block, block]}))


def test_repository_register():
    demos = load_demos(Path(__file__).with_name("complexity-manifest.json"))
    assert "legacy-data-migration" in demos
    assert [c["id"] for c in demos["legacy-data-migration"]["classes"]] == [f"MIG-0{i}" for i in range(1, 8)]
