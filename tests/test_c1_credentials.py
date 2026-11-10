import importlib.util
from pathlib import Path
import runpy
import secrets
import stat

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("script", ["scripts/seed.py", "testdata/generated/seed/helpers.py", "testdata/harness/validate.py"])
def test_seed_tools_read_environment(script, monkeypatch):
    value = secrets.token_urlsafe(24)
    monkeypatch.setenv("DB_PASSWORD", value)
    assert runpy.run_path(str(ROOT / script))["DB_CONFIG"]["password"] == value
    monkeypatch.delenv("DB_PASSWORD")
    assert runpy.run_path(str(ROOT / script))["DB_CONFIG"]["password"] is None


def test_local_env_creation_and_no_overwrite(tmp_path):
    spec = importlib.util.spec_from_file_location("local_env", ROOT / "scripts/local-env.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    path = tmp_path / ".env"
    module.initialize(path)
    values = dict(line.split("=", 1) for line in path.read_text().splitlines())
    assert set(values) == {"DB_PASSWORD", "BILLING_SVC_DB_PASSWORD"}
    assert len(set(values.values())) == 2
    assert all(len(value) == 64 for value in values.values())
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    content = path.read_text()
    with pytest.raises(RuntimeError, match="already exists"):
        module.initialize(path)
    assert path.read_text() == content
