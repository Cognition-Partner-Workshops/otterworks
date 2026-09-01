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

from custbill import bronze_rows_from_file, silver_rows_from_file


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
    source = generated_root / "bronze_source.dat"
    rows = bronze_rows_from_file(source)
    assert rows
    assert rows[0]["record_kind"] == "HDR"
    assert rows[-1]["record_kind"] == "TRL"
    assert all(row["source_file"] == source.name for row in rows)
    assert [row["line_no"] for row in rows] == list(range(1, len(rows) + 1))
    assert len({row["file_sha256"] for row in rows}) == 1


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
