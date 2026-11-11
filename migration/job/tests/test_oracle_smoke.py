"""scripts/oracle_smoke.py leaves no temporary directory behind."""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "oracle_smoke.py"


def _load():
    spec = importlib.util.spec_from_file_location("oracle_smoke_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("fails", [False, True])
def test_main_removes_its_local_dir(monkeypatch, fails):
    smoke = _load()
    seen = []

    def fake_smoke(local_dir):
        assert local_dir.is_dir()
        assert local_dir.stat().st_mode & 0o077 == 0
        seen.append(local_dir)
        if fails:
            raise RuntimeError("smoke failed")
        return 0

    monkeypatch.setattr(smoke, "smoke", fake_smoke)
    if fails:
        with pytest.raises(RuntimeError):
            smoke.main()
    else:
        assert smoke.main() == 0
    assert len(seen) == 1 and not seen[0].exists()
