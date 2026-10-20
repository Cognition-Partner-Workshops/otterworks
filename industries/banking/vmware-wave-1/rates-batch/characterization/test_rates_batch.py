"""Characterization tests for rates-batch, run as a black box through a runner script.

A runner takes `<in-dir> <out-dir> [yyyy-mm-dd]` (host paths), runs the job once,
prints everything the job wrote to stdout/stderr and exits with the job's exit code.
CHAR_TZ is the zone the runner gives the job for the "yesterday" default.

    RATES_RUN=characterization/run-vm.sh        pytest characterization   # VM stand-in
    RATES_RUN=characterization/run-container.sh pytest characterization   # container

The golden spool files were recorded from the VM stand-in (`wave1/rates-batch-vm`,
JRE 11, run-rates.sh) on data/rates/in. RECORD=1 rewrites them; only do that
against the VM stand-in.
"""
import datetime as dt
import os
import shutil
import subprocess
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

HERE = Path(__file__).parent
GOLDEN = HERE / "golden"
SEED_IN = HERE.parents[1] / "data" / "rates" / "in"
RUNNER = os.environ.get("RATES_RUN", str(HERE / "run-vm.sh"))
RECORD = os.environ.get("RECORD") == "1"
DAYS = ["2026-10-14", "2026-10-15", "2026-10-16"]
HEADER = "pair,open,high,low,close,avg_mid,ticks\n"
IN_PATH = "/var/spool/rates/in"
OUT_PATH = "/var/spool/rates/out"


def run(in_dir, out_dir, day=None, tz=None):
    args = [RUNNER, str(in_dir), str(out_dir)] + ([day] if day else [])
    env = dict(os.environ)
    if tz:
        env["CHAR_TZ"] = tz
    p = subprocess.run(args, capture_output=True, text=True, env=env, timeout=120)
    return p.returncode, p.stdout + p.stderr


def golden(name, data):
    f = GOLDEN / name
    if RECORD:
        f.write_bytes(data)
    assert f.exists(), f"missing golden file {f}; record it against the VM stand-in with RECORD=1"
    assert data == f.read_bytes()


@pytest.fixture
def out_dir(tmp_path):
    d = tmp_path / "out"
    d.mkdir()
    d.chmod(0o777)
    return d


@pytest.fixture
def in_dir(tmp_path):
    d = tmp_path / "in"
    d.mkdir()
    d.chmod(0o755)
    return d


def put_ticks(in_dir, day, text):
    f = in_dir / f"ticks-{day}.csv"
    f.write_text(text, encoding="utf-8")
    f.chmod(0o644)
    return f


def seed_ticks(day):
    return (SEED_IN / f"ticks-{day}.csv").read_text(encoding="utf-8")


def listing(d):
    return sorted(p.name for p in d.iterdir())


@pytest.mark.parametrize("day", DAYS)
def test_seeded_day(day, out_dir):
    rc, out = run(SEED_IN, out_dir, day)
    assert rc == 0, out
    assert f"rates {day}: 5 pairs written to {OUT_PATH}" in out
    assert listing(out_dir) == [f"rates-{day}.csv"]
    golden(f"rates-{day}.csv", (out_dir / f"rates-{day}.csv").read_bytes())


def test_seeded_day_shape():
    for day in DAYS:
        lines = (GOLDEN / f"rates-{day}.csv").read_text(encoding="utf-8").splitlines(keepends=True)
        assert lines[0] == HEADER
        pairs = [l.split(",")[0] for l in lines[1:]]
        assert pairs == sorted(pairs) and len(pairs) == 5
        assert all(l.endswith(",24\n") for l in lines[1:])


def test_all_days_share_one_spool(out_dir):
    for day in DAYS:
        rc, out = run(SEED_IN, out_dir, day)
        assert rc == 0, out
    assert listing(out_dir) == [f"rates-{d}.csv" for d in DAYS]
    for day in DAYS:
        assert (out_dir / f"rates-{day}.csv").read_bytes() == (GOLDEN / f"rates-{day}.csv").read_bytes()


def test_rerun_replaces_existing_file(out_dir):
    stale = out_dir / "rates-2026-10-15.csv"
    stale.write_text("stale\n")
    stale.chmod(0o666)
    rc, out = run(SEED_IN, out_dir, "2026-10-15")
    assert rc == 0, out
    assert listing(out_dir) == ["rates-2026-10-15.csv"]
    assert stale.read_bytes() == (GOLDEN / "rates-2026-10-15.csv").read_bytes()


def test_missing_ticks_exit_1(out_dir):
    rc, out = run(SEED_IN, out_dir, "2026-10-13")
    assert rc == 1
    assert f"no ticks for 2026-10-13 in {IN_PATH}" in out
    assert listing(out_dir) == []


def yesterdays(tz):
    before = dt.datetime.now(ZoneInfo(tz)).date() - dt.timedelta(days=1)
    return before


@pytest.mark.parametrize("tz", ["UTC", "Pacific/Kiritimati", "Etc/GMT+12", "Europe/London"])
def test_default_day_is_yesterday_in_zone(tz, in_dir, out_dir):
    before = yesterdays(tz)
    rc, out = run(in_dir, out_dir, tz=tz)
    after = yesterdays(tz)
    assert rc == 1
    assert any(f"no ticks for {d.isoformat()} in {IN_PATH}" in out for d in {before, after}), out
    assert listing(out_dir) == []


def test_default_day_success(in_dir, out_dir):
    day = yesterdays("UTC").isoformat()
    put_ticks(in_dir, day, seed_ticks("2026-10-16"))
    rc, out = run(in_dir, out_dir, tz="UTC")
    if rc == 1 and "no ticks for" in out:  # crossed midnight between put and run
        day = yesterdays("UTC").isoformat()
        put_ticks(in_dir, day, seed_ticks("2026-10-16"))
        rc, out = run(in_dir, out_dir, tz="UTC")
    assert rc == 0, out
    assert f"rates {day}: 5 pairs written to {OUT_PATH}" in out
    assert (out_dir / f"rates-{day}.csv").read_bytes() == (GOLDEN / "rates-2026-10-16.csv").read_bytes()


def test_header_only_ticks(in_dir, out_dir):
    put_ticks(in_dir, "2026-10-17", "timestamp,pair,bid,ask\n")
    rc, out = run(in_dir, out_dir, "2026-10-17")
    assert rc == 0, out
    assert f"rates 2026-10-17: 0 pairs written to {OUT_PATH}" in out
    assert (out_dir / "rates-2026-10-17.csv").read_text() == HEADER


def test_blank_lines_and_extra_header_skipped(in_dir, out_dir):
    lines = seed_ticks("2026-10-16").splitlines(keepends=True)
    text = "".join(lines[:10]) + "\n   \n" + "timestamp,pair,bid,ask\n" + "".join(lines[10:]) + "\n"
    put_ticks(in_dir, "2026-10-16", text)
    rc, out = run(in_dir, out_dir, "2026-10-16")
    assert rc == 0, out
    assert (out_dir / "rates-2026-10-16.csv").read_bytes() == (GOLDEN / "rates-2026-10-16.csv").read_bytes()


def test_whitespace_around_fields(in_dir, out_dir):
    lines = seed_ticks("2026-10-14").splitlines()
    spaced = [lines[0]] + [",".join(" " + f + " " if i else f for i, f in enumerate(l.split(","))) for l in lines[1:]]
    put_ticks(in_dir, "2026-10-14", "\n".join(spaced) + "\n")
    rc, out = run(in_dir, out_dir, "2026-10-14")
    assert rc == 0, out
    assert (out_dir / "rates-2026-10-14.csv").read_bytes() == (GOLDEN / "rates-2026-10-14.csv").read_bytes()


def test_rounding_half_even(in_dir, out_dir):
    put_ticks(in_dir, "2026-10-18", "timestamp,pair,bid,ask\n"
              "2026-10-18T00:00:00,AAABBB,1.0000005,1.0000000\n"
              "2026-10-18T01:00:00,AAABBB,1.0000015,1.0000000\n"
              "2026-10-18T02:00:00,AAABBB,1.0000010,1.0000010\n")
    rc, out = run(in_dir, out_dir, "2026-10-18")
    assert rc == 0, out
    golden("rates-rounding-2026-10-18.csv", (out_dir / "rates-2026-10-18.csv").read_bytes())


def test_malformed_number_fails_whole_day(in_dir, out_dir):
    put_ticks(in_dir, "2026-10-19", "timestamp,pair,bid,ask\n"
              "2026-10-19T00:00:00,EURUSD,1.0800,1.0802\n"
              "2026-10-19T01:00:00,EURUSD,abc,1.0812\n")
    rc, out = run(in_dir, out_dir, "2026-10-19")
    assert rc == 1
    assert "java.lang.NumberFormatException" in out
    assert listing(out_dir) == []


def test_short_line_fails_whole_day(in_dir, out_dir):
    put_ticks(in_dir, "2026-10-19", "timestamp,pair,bid,ask\n2026-10-19T00:00:00,EURUSD,1.0800\n")
    rc, out = run(in_dir, out_dir, "2026-10-19")
    assert rc == 1
    assert "java.lang.ArrayIndexOutOfBoundsException" in out
    assert listing(out_dir) == []


def test_bad_date_argument(out_dir):
    rc, out = run(SEED_IN, out_dir, "2026-13-01")
    assert rc == 1
    assert "java.time.format.DateTimeParseException" in out
    assert listing(out_dir) == []


def test_input_spool_untouched(out_dir):
    before = {p.name: p.read_bytes() for p in SEED_IN.iterdir()}
    for day in DAYS:
        run(SEED_IN, out_dir, day)
    assert {p.name: p.read_bytes() for p in SEED_IN.iterdir()} == before
