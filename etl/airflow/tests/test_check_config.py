"""check_config.py static: etl/config.ini stays deleted; mapped values survive script retirement."""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import pytest

AIRFLOW_DIR = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "check_config", AIRFLOW_DIR / "scripts" / "check_config.py"
)
check_config = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_config)


SCRIPTS_DIR = AIRFLOW_DIR.parent / "scripts"


def _root(tmp_path: Path, scripts: bool = False) -> Path:
    airflow = tmp_path / "etl" / "airflow"
    airflow.mkdir(parents=True)
    for name in ("CONFIG.md", ".env.example"):
        shutil.copy(AIRFLOW_DIR / name, airflow / name)
    if scripts:
        shutil.copytree(SCRIPTS_DIR, tmp_path / "etl" / "scripts")
    return tmp_path


def test_static_passes_without_config_ini(tmp_path):
    assert check_config.check_static(_root(tmp_path)) == []


def test_static_fails_when_config_ini_comes_back(tmp_path):
    root = _root(tmp_path)
    (root / "etl" / "config.ini").write_text("[aws]\n")
    errors = check_config.check_static(root)
    assert errors == [
        "etl/config.ini: retired (ETL_UPGRADE_GUIDE.md step 9); configuration is the "
        "Connections and Variables in etl/airflow/CONFIG.md"
    ]


@pytest.mark.skipif(not SCRIPTS_DIR.is_dir(), reason="etl/scripts not mounted or all retired")
def test_script_defaults_are_checked_while_the_scripts_exist(tmp_path, capsys):
    root = _root(tmp_path, scripts=True)
    assert check_config.check_static(root) == []
    assert "0 checked against etl/scripts" not in capsys.readouterr().out
    script = root / "etl" / "scripts" / "user_activity_daily.py"
    script.write_text(script.read_text().replace("lookback_days = 30", "lookback_days = 31"))
    assert any("user_activity_lookback_days" in e for e in check_config.check_static(root))


def test_retired_scripts_are_skipped_but_config_md_still_matches_env(tmp_path, capsys):
    root = _root(tmp_path)
    assert check_config.check_static(root) == []
    assert "(0 checked against etl/scripts)" in capsys.readouterr().out
    example = root / "etl" / "airflow" / ".env.example"
    example.write_text(
        example.read_text().replace(
            "AIRFLOW_VAR_USER_ACTIVITY_LOOKBACK_DAYS=30",
            "AIRFLOW_VAR_USER_ACTIVITY_LOOKBACK_DAYS=31",
        )
    )
    assert any("CONFIG.md value '30'" in e for e in check_config.check_static(root))
