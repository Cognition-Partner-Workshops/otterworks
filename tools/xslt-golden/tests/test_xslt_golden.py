import os
import shutil
import sys

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import xslt_golden  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "fixture")


def _manifest(tmp_path, golden_dir):
    shutil.copytree(FIXTURE, tmp_path / "fixture")
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(yaml.safe_dump({
        "base": "fixture",
        "maps": [{"name": "upper", "xslt": "upper.xslt", "inputs": "in", "golden": golden_dir,
                  "params": {"Suffix": "!"}}],
    }))
    return str(manifest)


def test_write_then_check(tmp_path):
    manifest = _manifest(tmp_path, "golden")
    assert xslt_golden.run(manifest, "write", None) == 0
    golden = tmp_path / "fixture" / "golden" / "one.xml"
    assert golden.read_bytes() == b"<shout>HELLO!</shout>"
    assert xslt_golden.run(manifest, "check", None) == 0


def test_check_reports_diff(tmp_path):
    manifest = _manifest(tmp_path, "golden")
    xslt_golden.run(manifest, "write", None)
    (tmp_path / "fixture" / "golden" / "one.xml").write_bytes(b"<shout>HELLO</shout>")
    assert xslt_golden.run(manifest, "check", None) == 1


def test_check_reports_missing(tmp_path):
    manifest = _manifest(tmp_path, "nowhere")
    assert xslt_golden.run(manifest, "check", None) == 1
