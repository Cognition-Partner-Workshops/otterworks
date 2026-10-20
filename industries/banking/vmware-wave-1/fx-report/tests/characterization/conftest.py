import os

import pytest


@pytest.fixture(scope="session")
def base_url() -> str:
    url = os.environ.get("BASE_URL")
    if not url:
        pytest.fail("set BASE_URL, e.g. BASE_URL=http://localhost:8086")
    return url.rstrip("/")


@pytest.fixture(scope="session")
def report_path() -> str:
    return os.environ.get("REPORT_PATH", "/fx/fx-report.cgi")


@pytest.fixture(scope="session")
def report_tz() -> str:
    return os.environ.get("REPORT_TZ", "UTC")
