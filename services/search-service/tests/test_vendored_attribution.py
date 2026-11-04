from pathlib import Path

import pytest


def test_vendored_attribution_matches_source():
    repo_root = Path(__file__).resolve().parents[3]
    source = repo_root / "workloads/attribution/sf_attribution.py"
    vendored = repo_root / "services/search-service/app/vendor/sf_attribution.py"
    if not source.is_file():
        pytest.skip("workloads attribution helper is not present in this build context")
    assert vendored.read_bytes() == source.read_bytes()
