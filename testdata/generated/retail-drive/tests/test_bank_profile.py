"""Bank-profile taxonomy, deterministic builders, and CLI checks."""
from __future__ import annotations

import io
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import pytest

DRIVE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DRIVE_DIR))

import bank_filegen  # noqa: E402
import bank_taxonomy  # noqa: E402
import generate_drive  # noqa: E402


def _sample_name(spec: dict) -> str:
    axes = []
    for axis in re.findall(r"{(\w+)}", spec["folder"] + " " + spec["name"]):
        if axis in bank_taxonomy.AXES and axis not in axes:
            axes.append(axis)
    values = {axis: bank_taxonomy.AXES[axis][0] for axis in axes}
    return spec["name"].format(**values)


def _docx_text(data: bytes) -> str:
    pieces = []
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for path in archive.namelist():
            if path.startswith("word/") and path.endswith(".xml"):
                root = ElementTree.fromstring(archive.read(path))
                pieces.extend(
                    node.text or ""
                    for node in root.iter()
                    if node.tag.endswith("}t")
                )
    return "\n".join(pieces)


def test_every_bank_department_expands_and_scale_one_is_bounded(monkeypatch):
    monkeypatch.setattr(generate_drive, "taxonomy", bank_taxonomy)
    counts = {
        dept: len(list(generate_drive.expand_specs(dept, 1.0)))
        for dept in bank_taxonomy.all_departments()
    }
    assert len(counts) == 8
    assert all(count > 0 for count in counts.values())
    assert 400 <= sum(counts.values()) <= 700


@pytest.mark.parametrize(
    ("name", "year"),
    [
        ("Consumer statement 2024.csv", 2024),
        ("Treasury activity 2026.json", 2026),
        ("Document without a year.md", 2025),
    ],
)
def test_transactions_start_in_the_filename_year(name, year):
    actual_year = bank_filegen._name_year(name)
    first = bank_filegen._transactions(bank_filegen._rng(name, 17), start_year=actual_year)
    second = bank_filegen._transactions(bank_filegen._rng(name, 17), start_year=actual_year)

    assert first == second
    assert first[0]["date"] == f"{year}-01-01"


def test_each_bank_spec_builds_small_deterministic_files_and_clean_text():
    banned = re.compile(r"otter|salmon|retailco", re.IGNORECASE)
    names = [str(dept) for dept in bank_taxonomy.DEPARTMENTS]
    names.extend(str(value) for values in bank_taxonomy.AXES.values() for value in values)
    for specs in bank_taxonomy.DEPARTMENTS.values():
        for spec in specs:
            names.extend([spec["folder"], spec["name"]])
    names.extend(title for titles in bank_taxonomy.DEPARTMENT_DOCS.values() for title in titles)
    assert not banned.search("\n".join(names))

    checked_text = 0
    for specs in bank_taxonomy.DEPARTMENTS.values():
        for spec in specs:
            ext = spec["type"]
            name = _sample_name(spec)
            first, mime = bank_filegen.build(ext, name, 20240117, kind=spec.get("kind"))
            second, second_mime = bank_filegen.build(ext, name, 20240117, kind=spec.get("kind"))
            assert mime == bank_filegen.MIME[ext] == second_mime
            assert len(first) < 1_000_000
            assert first == second
            if ext == "docx":
                text = _docx_text(first)
                checked_text += 1
            elif ext in {"md", "csv"}:
                text = first.decode("utf-8")
                checked_text += 1
            elif ext == "json":
                text = json.dumps(json.loads(first), ensure_ascii=False)
                checked_text += 1
            else:
                continue
            assert not banned.search(text), f"forbidden text in {name}.{ext}"
    assert checked_text > 0


def test_bank_dry_run_succeeds_and_retail_dry_run_is_unchanged(capsys):
    args = ["--gateway", "x", "--email", "x", "--password", "x",
            "--departments", "all", "--scale", "1.0", "--dry-run"]
    assert generate_drive.main(["--profile", "bank", *args]) == 0
    bank_lines = capsys.readouterr().out.splitlines()
    total = next(line for line in bank_lines if "TOTAL" in line)
    assert int(total.split()[1]) in range(400, 701)
    assert total.endswith("files across 8 departments")

    baseline = [
        ("Finance", 213),
        ("Human Resources", 133),
        ("Legal", 49),
        ("Marketing", 144),
        ("Merchandising", 140),
        ("Store Operations", 286),
        ("Supply Chain & Logistics", 241),
        ("E-Commerce", 52),
        ("Information Technology", 21),
        ("Procurement", 191),
        ("Customer Service", 76),
        ("Real Estate & Facilities", 144),
        ("Loss Prevention", 277),
        ("Analytics & Insights", 149),
        ("Executive", 56),
    ]
    expected = "".join(
        f"  {dept:28s} {count:5d} files\n" for dept, count in baseline
    )
    expected += f"  {'TOTAL':28s} {2172:5d} files across 15 departments\n"

    assert generate_drive.main(args) == 0
    default_output = capsys.readouterr().out
    assert default_output == expected
    assert generate_drive.main(["--profile", "retail", *args]) == 0
    assert capsys.readouterr().out == expected
