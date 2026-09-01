from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SCRIPT_DIR.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from custbill import bronze_rows_from_file, legacy_dat_files, silver_rows_from_file


@pytest.fixture(scope="session")
def generated_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("custbill-legacy")
    env = os.environ.copy()
    env["OTTERWORKS_LEGACY_ROOT"] = str(root)
    subprocess.run(
        ["make", "legacy-etl-gen-data", "NS=w0test"],
        cwd=REPO_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    source = root / "sftp-drop" / "upload" / "CUSTBILL_W0TEST_001.dat"
    shutil.copyfile(source, root / "bronze_source.dat")
    env["RUN_ALL_SLEEP"] = "0"
    subprocess.run(
        ["make", "legacy-etl-run", "JOB=run_all"],
        cwd=REPO_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return root


def test_bronze_rows_from_generated_dat(generated_root: Path) -> None:
    files = legacy_dat_files(generated_root)
    assert files[0][0].endswith(".dat")
    assert files[0][1].name.endswith(".dat.done")
    rows = bronze_rows_from_file(files[0][1], files[0][0])
    assert rows
    assert rows[0]["record_kind"] == "HDR"
    assert rows[-1]["record_kind"] == "TRL"
    assert all(row["source_file"] == files[0][0] for row in rows)
    assert [row["line_no"] for row in rows] == list(range(1, len(rows) + 1))
    assert len({row["file_sha256"] for row in rows}) == 1


def test_bronze_rows_preserve_latin1_and_newline_only(tmp_path: Path) -> None:
    source = tmp_path / "CUSTBILL_BYTE.dat.done"
    source.write_bytes(b"HDR header\r\ncaf\xe9\x0bbody\n")
    rows = bronze_rows_from_file(source, "CUSTBILL_BYTE.dat")
    assert rows[1]["raw_line"] == "caf\xe9\x0bbody"
    assert rows[1]["raw_line"].encode("latin-1") == b"caf\xe9\x0bbody"


def test_silver_rows_from_generated_psv(generated_root: Path) -> None:
    parsed = generated_root / "parsed" / "CUSTBILL_W0TEST_001.psv"
    rows = silver_rows_from_file(parsed)
    assert rows
    assert rows[0]["source_file"] == "CUSTBILL_W0TEST_001.dat"
    assert rows[0]["line_no"] == 1
    assert set(rows[0]) == {
        "source_file", "line_no", "cust_id", "cust_name", "bill_date",
        "bill_amt", "currency", "rec_type",
    }
