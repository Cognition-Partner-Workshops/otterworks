"""Shared runtime for the Python ports of the CUSTBILL batch chain.

Reproduces the environment the legacy jobs read (hostname branches, the
OTTERWORKS_LEGACY_ROOT fallback, the never-removed /tmp lock files and the
two timestamp formats they print) so each port can stay byte-identical.

Test seams (unset in production, set by tools/parity.sh and the tests):
  CUSTBILL_NOW       freeze the clock, "YYYY-MM-DD HH:MM:SS" in local time
  CUSTBILL_LOCK_DIR  directory holding the lock files (default /tmp)
"""

from __future__ import annotations

import os
import socket
import time
from pathlib import Path

PROD_HOST = "otterworks-etl-prod-01"
UAT_HOST = "otterworks-etl-uat"
DEFAULT_DEV_ROOT = "/tmp/otterworks-legacy"


def host_profile(hostname: str | None = None) -> str:
    """Return "prod", "uat" or "dev" the way the legacy hostname if-blocks do."""
    name = socket.gethostname() if hostname is None else hostname
    if name == PROD_HOST:
        return "prod"
    if name == UAT_HOST:
        return "uat"
    return "dev"


def legacy_root(profile: str | None = None, environ: dict | None = None) -> Path:
    """ROOT as the legacy jobs compute it (empty OTTERWORKS_LEGACY_ROOT counts as unset)."""
    env = os.environ if environ is None else environ
    profile = host_profile() if profile is None else profile
    if profile == "prod":
        return Path("/data/otterworks")
    if profile == "uat":
        return Path("/data2/otterworks_uat")
    return Path(env.get("OTTERWORKS_LEGACY_ROOT") or DEFAULT_DEV_ROOT)


def now_epoch(environ: dict | None = None) -> float:
    env = os.environ if environ is None else environ
    frozen = env.get("CUSTBILL_NOW")
    if frozen:
        return time.mktime(time.strptime(frozen, "%Y-%m-%d %H:%M:%S"))
    return time.time()


def date_cmd_stamp(epoch: float) -> str:
    """What a bare `date` prints under LC_ALL=C, e.g. "Thu Jan 15 00:00:00 UTC 2026"."""
    return time.strftime("%a %b %e %H:%M:%S %Z %Y", time.localtime(epoch))


def perl_localtime_stamp(epoch: float) -> str:
    """What Perl's scalar(localtime) prints, e.g. "Thu Jan 15 00:00:00 2026"."""
    return time.strftime("%a %b %e %H:%M:%S %Y", time.localtime(epoch))


def lock_path(name: str, environ: dict | None = None) -> Path:
    env = os.environ if environ is None else environ
    return Path(env.get("CUSTBILL_LOCK_DIR") or "/tmp") / name


def check_and_touch_lock(path: Path, present_message: str) -> None:
    """Legacy lock pattern: warn if present, touch it, never remove it."""
    if path.is_file():
        print(present_message)
    try:
        path.touch()
    except OSError:
        pass
