from pathlib import Path

import custbill_common as cc


def test_host_profile_matches_legacy_hostname_branches():
    assert cc.host_profile("otterworks-etl-prod-01") == "prod"
    assert cc.host_profile("otterworks-etl-uat") == "uat"
    assert cc.host_profile("laptop") == "dev"


def test_legacy_root_branches_and_empty_env_fallback():
    assert cc.legacy_root("prod", {}) == Path("/data/otterworks")
    assert cc.legacy_root("uat", {}) == Path("/data2/otterworks_uat")
    assert cc.legacy_root("dev", {"OTTERWORKS_LEGACY_ROOT": "/x"}) == Path("/x")
    assert cc.legacy_root("dev", {"OTTERWORKS_LEGACY_ROOT": ""}) == Path("/tmp/otterworks-legacy")
    assert cc.legacy_root("dev", {}) == Path("/tmp/otterworks-legacy")


def test_frozen_clock_and_legacy_stamp_formats(monkeypatch):
    monkeypatch.setenv("TZ", "UTC")
    import time
    time.tzset()
    epoch = cc.now_epoch({"CUSTBILL_NOW": "2026-01-05 03:04:05"})
    assert cc.date_cmd_stamp(epoch) == "Mon Jan  5 03:04:05 UTC 2026"
    assert cc.perl_localtime_stamp(epoch) == "Mon Jan  5 03:04:05 2026"


def test_lock_is_touched_warned_and_never_removed(tmp_path, capsys):
    lock = cc.lock_path("x.lock", {"CUSTBILL_LOCK_DIR": str(tmp_path)})
    cc.check_and_touch_lock(lock, "lock present")
    assert lock.is_file() and capsys.readouterr().out == ""
    cc.check_and_touch_lock(lock, "lock present")
    assert lock.is_file() and capsys.readouterr().out == "lock present\n"


def test_lock_touch_failure_is_swallowed(tmp_path, capsys):
    cc.check_and_touch_lock(tmp_path / "missing-dir" / "x.lock", "lock present")
    assert capsys.readouterr().out == ""
