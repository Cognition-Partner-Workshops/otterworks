import math
import os
import shutil
import subprocess
from pathlib import Path

import golden_replay
import pytest

import finance_excel_report as fer

JOB = "finance_excel_report"
STAMP = "Thu Jan 15 00:00:00 2026"
REPORT = "reports/finance_billing_20260115"


def stdout_lines(proc):
    return proc.stdout.decode().splitlines()


def run(root: Path, lock_dir: Path):
    lock_dir.mkdir(exist_ok=True)
    return golden_replay.run_port(JOB, root, lock_dir)


def test_golden_covers_dev_and_qa():
    assert {"dev", "qa"} <= set(golden_replay.golden_namespaces(JOB))


@pytest.mark.parametrize("ns", golden_replay.golden_namespaces(JOB))
def test_golden_replay(ns, tmp_path):
    expected, actual = golden_replay.replay(JOB, ns, tmp_path)
    golden_replay.assert_matches(expected, actual)


def test_fresh_root_writes_header_only_report_and_exits_0(tmp_path):
    root = tmp_path / "root"
    proc = run(root, tmp_path / "locks")
    assert proc.returncode == 0 and proc.stderr == b""
    assert stdout_lines(proc) == [
        f"{STAMP} finance_excel_report starting",
        f"{STAMP} wrote {root}/{REPORT}.xls",
        f"{STAMP} finance_excel_report done",
    ]
    csv = (root / f"{REPORT}.csv").read_bytes()
    assert csv == b"Currency,RecordType,RecordCount,TotalAmount\n"
    assert (root / f"{REPORT}.xls").read_bytes() == csv
    assert sorted(p.name for p in root.iterdir()) == ["parsed", "reports"]
    assert (tmp_path / "locks" / "finance_report.lock").is_file()


def test_present_lock_warns_continues_and_is_left_in_place(tmp_path):
    lock = tmp_path / "locks" / "finance_report.lock"
    lock.parent.mkdir()
    lock.write_bytes(b"stale")
    proc = run(tmp_path / "root", lock.parent)
    assert proc.returncode == 0
    assert stdout_lines(proc)[0] == "finance report lock present, running anyway"
    assert stdout_lines(proc)[-1] == f"{STAMP} finance_excel_report done"
    assert lock.is_file() and lock.read_bytes() == b""


def test_non_matching_names_and_directories_are_ignored(tmp_path):
    parsed = tmp_path / "root" / "parsed"
    parsed.mkdir(parents=True)
    row = b"C1|N|2026-01-01|10.00|USD|01\n"
    for name in ("custbill_a.psv", "XCUSTBILL_a.psv", "CUSTBILL_a.psv.bak", "CUSTBILL_a.txt", "CUSTBILL_b.psv"):
        (parsed / name).write_bytes(row)
    (parsed / "CUSTBILL_dir.psv").mkdir()
    proc = run(tmp_path / "root", tmp_path / "locks")
    assert proc.returncode == 0
    assert (tmp_path / "root" / f"{REPORT}.csv").read_bytes().splitlines()[1:] == [b"USD,INVOICE,1,10.00"]
    assert sorted(p.name for p in parsed.iterdir()) == sorted(
        ["custbill_a.psv", "XCUSTBILL_a.psv", "CUSTBILL_a.psv.bak", "CUSTBILL_a.txt", "CUSTBILL_b.psv", "CUSTBILL_dir.psv"]
    )


EDGE_ROWS = (
    b"C1|A|2026-01-01|1.005|USD|01\n"
    b"|empty cust skipped|x|999|USD|01\n"
    b"\n"
    b"C2|B|x|  2.5abc|USD|01\n"
    b"C3|short\n"
    b"C4|C|x|-.5e1|eur|09\n"
    b"C5|D|x|0x10|EUR|02\n"
    b"C6|E|x|1e|EUR|02|extra|fields\n"
    b"C7|F|x|inf|GBP|01\n"
    b"C8|G|x|nan|GBP|02\n"
    b"C9|H|x|7.10|USD|01"
)


def test_edge_rows_follow_perl_split_numification_and_byte_sort(tmp_path):
    parsed = tmp_path / "root" / "parsed"
    parsed.mkdir(parents=True)
    (parsed / "CUSTBILL_edge.psv").write_bytes(EDGE_ROWS)
    proc = run(tmp_path / "root", tmp_path / "locks")
    assert proc.returncode == 0
    assert (tmp_path / "root" / f"{REPORT}.csv").read_bytes() == (
        b"Currency,RecordType,RecordCount,TotalAmount\n"
        b"EUR,CREDIT,2,1.00\n"
        b"GBP,INVOICE,1,Inf\n"
        b"GBP,CREDIT,1,NaN\n"
        b"USD,INVOICE,3,10.61\n"
        b"eur,UNKNOWN(09),1,-5.00\n"
        b",UNKNOWN(),1,0.00\n"
    )


def test_files_are_summed_in_byte_order(tmp_path):
    parsed = tmp_path / "root" / "parsed"
    parsed.mkdir(parents=True)
    (parsed / "CUSTBILL_b.psv").write_bytes(b"C|N|d|0.1|USD|01\n")
    (parsed / "CUSTBILL_B.psv").write_bytes(b"C|N|d|1e16|USD|01\n")
    (parsed / "CUSTBILL_a.psv").write_bytes(b"C|N|d|-1e16|USD|01\n")
    run(tmp_path / "root", tmp_path / "locks")
    # B < a < b: (1e16 + -1e16) + 0.1 = 0.1, whereas a,b,B order would give 0.00
    assert (tmp_path / "root" / f"{REPORT}.csv").read_bytes().splitlines()[1] == b"USD,INVOICE,3,0.10"


@pytest.mark.parametrize(
    "raw, value",
    [(b"12.34", 12.34), (b" \t12.5x", 12.5), (b"+.5", 0.5), (b"-.5e1", -5.0), (b"1e", 1.0), (b"1e3", 1000.0),
     (b"0x10", 0.0), (b"", 0.0), (b"abc", 0.0), (b"1_000", 1.0), (b"\x0b7", 7.0), (b"-Infinity", -math.inf),
     (b"infinit", math.inf)],
)
def test_perl_num(raw, value):
    assert fer.perl_num(raw) == value


def test_perl_f2_special_values():
    assert fer.perl_f2(math.inf) == "Inf"
    assert fer.perl_f2(-math.inf) == "-Inf"
    assert fer.perl_f2(math.nan) == "NaN"
    assert fer.perl_f2(fer.perl_num(b"nan")) == "NaN"
    assert fer.perl_f2(0.0 + fer.perl_num(b"-0")) == "0.00"
    assert fer.perl_f2(2.675) == "2.67"


def test_parsed_not_a_directory_dies_like_perl(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "parsed").write_bytes(b"")
    proc = run(root, tmp_path / "locks")
    assert proc.returncode == 20
    assert proc.stderr.decode() == f"cannot open {root}/parsed: Not a directory at {fer.LEGACY_SCRIPT} line 43.\n"
    assert stdout_lines(proc) == [f"{STAMP} finance_excel_report starting"]


def test_unwritable_report_dies_like_perl(tmp_path):
    root = tmp_path / "root"
    (root / "parsed").mkdir(parents=True)
    (root / "reports").write_bytes(b"")
    proc = run(root, tmp_path / "locks")
    assert proc.returncode == 20
    assert proc.stderr.decode() == (
        f"cannot write {root}/{REPORT}.csv: Not a directory at {fer.LEGACY_SCRIPT} line 65.\n"
    )


@pytest.mark.parametrize(
    "profile, mailto",
    [("prod", "finance-reports@otterworks.dev"), ("uat", "jake@otterworks.dev"), ("dev", "dev-null@localhost")],
)
def test_sendmail_stub_receives_report_notice(tmp_path, monkeypatch, profile, mailto):
    out = tmp_path / "mail.txt"
    stub = tmp_path / "sendmail"
    stub.write_text(f'#!/bin/sh\n[ "$1" = -t ] && cat > {out}\n')
    stub.chmod(0o755)
    root = tmp_path / "root"
    monkeypatch.setattr(fer, "SENDMAIL", str(stub))
    monkeypatch.setattr(fer.cc, "host_profile", lambda: profile)
    monkeypatch.setattr(fer.cc, "legacy_root", lambda _profile: root)
    monkeypatch.setenv("CUSTBILL_LOCK_DIR", str(tmp_path))
    monkeypatch.setenv("CUSTBILL_NOW", "2026-01-15 00:00:00")
    assert fer.main() == 0
    assert out.read_text() == (
        f"To: {mailto}\nSubject: [AUTO] Finance billing report 20260115\n\n"
        f"Attached... well, saved to {root}/{REPORT}.xls on the ETL box.\n"
    )


def test_missing_sendmail_is_silent(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(fer, "SENDMAIL", str(tmp_path / "no-sendmail"))
    monkeypatch.setenv("OTTERWORKS_LEGACY_ROOT", str(tmp_path / "root"))
    monkeypatch.setenv("CUSTBILL_LOCK_DIR", str(tmp_path))
    assert fer.main() == 0
    captured = capsys.readouterr()
    assert captured.err == "" and captured.out.endswith("finance_excel_report done\n")


@pytest.mark.skipif(shutil.which("perl") is None, reason="perl not installed")
def test_edge_rows_match_legacy_perl(tmp_path):
    estate = Path(fer.__file__).resolve().parent.parent
    roots = {}
    for side in ("legacy", "python"):
        root = tmp_path / side
        (root / "parsed").mkdir(parents=True)
        (root / "parsed" / "CUSTBILL_edge.psv").write_bytes(EDGE_ROWS)
        roots[side] = root
    env = dict(os.environ, OTTERWORKS_LEGACY_ROOT=str(roots["legacy"]), CUSTBILL_NOW=golden_replay.GOLDEN_NOW,
               TZ="UTC", LC_ALL="C", PERL5LIB=str(estate / "tools" / "detclock"), PERL5OPT="-MCustbillDetClock")
    legacy = subprocess.run(["perl", str(fer.LEGACY_SCRIPT)], env=env, capture_output=True, check=False)
    run(roots["python"], tmp_path / "locks")
    assert legacy.returncode == 0
    for suffix in (".csv", ".xls"):
        assert (roots["python"] / f"{REPORT}{suffix}").read_bytes() == (roots["legacy"] / f"{REPORT}{suffix}").read_bytes()
