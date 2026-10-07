"""check_config.py static: etl/config.ini stays deleted."""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

AIRFLOW_DIR = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "check_config", AIRFLOW_DIR / "scripts" / "check_config.py"
)
check_config = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_config)


def _root(tmp_path: Path) -> Path:
    airflow = tmp_path / "etl" / "airflow"
    airflow.mkdir(parents=True)
    for name in ("CONFIG.md", ".env.example"):
        shutil.copy(AIRFLOW_DIR / name, airflow / name)
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
