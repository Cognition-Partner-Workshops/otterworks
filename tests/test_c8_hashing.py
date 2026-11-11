import importlib.util
from pathlib import Path

import bcrypt
import pytest


@pytest.mark.parametrize("relative_path", ["scripts/seed.py", "testdata/generated/seed/helpers.py"])
def test_seed_password_hashes_use_cost_12(relative_path):
    path = Path(__file__).resolve().parents[1] / relative_path
    spec = importlib.util.spec_from_file_location("seed_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    hashed = module.hash_password("seed-password").encode()
    assert hashed.split(b"$")[2] == b"12"
    assert bcrypt.checkpw(b"seed-password", hashed)
    assert not bcrypt.checkpw(b"wrong-password", hashed)


def test_compose_document_service_gets_share_link_secret():
    import yaml
    compose = yaml.safe_load((Path(__file__).resolve().parents[1] / "docker-compose.yml").read_text())
    assert compose["services"]["document-service"]["environment"].get("SHARE_LINK_SECRET")


@pytest.mark.parametrize("script", ["scripts/lib/tenant-common.sh", "scripts/deploy-dev.sh"])
def test_share_link_secret_survives_db_password_rotation(script, tmp_path):
    import base64
    import re
    import subprocess

    root = Path(__file__).resolve().parents[1]
    fn = re.search(r"^share_link_secret\(\) \{.*?^\}", (root / script).read_text(), re.S | re.M)
    assert fn, "share_link_secret() helper missing"
    stub = tmp_path / "kubectl"
    stub.write_text("#!/bin/sh\n[ -f \"$EXISTING\" ] && cat \"$EXISTING\"\n")
    stub.chmod(0o755)

    def run(db_password, existing=None):
        env = {"PATH": f"{tmp_path}:/usr/bin:/bin", "DB_PASSWORD": db_password,
               "EXISTING": str(tmp_path / "existing")}
        if existing:
            (tmp_path / "existing").write_text(base64.b64encode(existing.encode()).decode())
        return subprocess.run(["bash", "-c", fn.group(0) + '\nshare_link_secret otterworks-t'],
                              env=env, capture_output=True, text=True, check=True).stdout

    assert run("old", "kept-secret") == run("rotated", "kept-secret") == "kept-secret"
    (tmp_path / "existing").unlink()
    fresh = run("old")
    assert re.fullmatch(r"[0-9a-f]{64}", fresh) and fresh != run("old")
