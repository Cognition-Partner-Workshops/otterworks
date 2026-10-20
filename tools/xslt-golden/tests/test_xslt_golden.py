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


def test_typed_params_and_output_encoding(tmp_path):
    xslt = tmp_path / "typed.xslt"
    xslt.write_text(
        '<xsl:stylesheet version="3.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform" '
        'xmlns:xs="http://www.w3.org/2001/XMLSchema" exclude-result-prefixes="xs">'
        '<xsl:output method="xml" encoding="ISO-8859-1" omit-xml-declaration="yes"/>'
        '<xsl:param name="Count" as="xs:integer"/><xsl:param name="Strict" as="xs:boolean"/>'
        '<xsl:template match="/"><r c="{$Count + 1}" s="{$Strict}">\u00e9</r></xsl:template>'
        '</xsl:stylesheet>', encoding="utf-8")
    (tmp_path / "in").mkdir()
    (tmp_path / "in" / "one.xml").write_text("<a/>")
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(yaml.safe_dump({"base": ".", "maps": [
        {"name": "typed", "xslt": "typed.xslt", "inputs": "in", "golden": "golden", "params": {"Count": 2, "Strict": True}}]}))
    assert xslt_golden.run(str(manifest), "write", None) == 0
    assert (tmp_path / "golden" / "one.xml").read_bytes() == b'<r c="3" s="true">\xe9</r>'
