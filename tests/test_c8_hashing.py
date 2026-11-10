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
