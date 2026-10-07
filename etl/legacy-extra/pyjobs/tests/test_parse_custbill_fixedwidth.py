from pathlib import Path

import pytest

import golden_replay
import parse_custbill_fixedwidth as parser

JOB = "parse_custbill_fixedwidth"
STAMP = b"Thu Jan 15 00:00:00 UTC 2026"
START = STAMP + b" parse_custbill starting\n"
END = STAMP + b" parse_custbill done\n"
WARNING = b"parse lock exists, probably stale, proceeding\n"


def record(amount=b"000000123456", date=b"20260115", customer=b"ID", name=b"NAME",
           ccy=b"USD", rt=b"01"):
    return (customer.ljust(10) + name.ljust(30) + date.ljust(8) + amount.ljust(12)
            + ccy.ljust(3) + rt)


@pytest.fixture
def estate(tmp_path):
    root, locks = tmp_path / "root", tmp_path / "locks"
    (root / "incoming").mkdir(parents=True)
    locks.mkdir()
    return root, locks


def run(estate):
    root, locks = estate
    return golden_replay.run_port(JOB, root, locks)


def parsed_line(name, count, trailer=b"?"):
    return STAMP + b" parsed " + name + b": " + str(count).encode() + b" records (trailer says " + trailer + b")\n"


def test_both_required_golden_namespaces_are_present():
    assert {"dev", "qa"} <= set(golden_replay.golden_namespaces(JOB))


@pytest.mark.parametrize("ns", golden_replay.golden_namespaces(JOB))
def test_golden_replay(ns, tmp_path, monkeypatch):
    run_port = golden_replay.run_port

    def run_from_recorded_before_state(job, root, lock_dir):
        before = golden_replay.GOLDEN / job / ns / "before/manifest"
        for line in before.read_text().splitlines():
            name, kind, _ = line.rsplit(" ", 2)
            if kind == "d":
                (root / name).mkdir(parents=True, exist_ok=True)
        assert golden_replay.manifest(root) == before.read_bytes()
        return run_port(job, root, lock_dir)

    monkeypatch.setattr(golden_replay, "run_port", run_from_recorded_before_state)
    expected, actual = golden_replay.replay(JOB, ns, tmp_path)
    golden_replay.assert_matches(expected, actual)


@pytest.mark.parametrize("existing_root", [False, True])
def test_empty_or_fresh_root_creates_only_parsed_and_retains_lock(tmp_path, existing_root):
    root, locks = tmp_path / "root", tmp_path / "locks"
    locks.mkdir()
    if existing_root:
        root.mkdir()
    proc = run((root, locks))
    assert (proc.returncode, proc.stdout, proc.stderr) == (0, START + END, b"")
    assert list(root.iterdir()) == [root / "parsed"]
    assert (locks / "parse_custbill.lock").read_bytes() == b""


def test_stale_lock_warns_run_continues_and_lock_is_not_removed(estate):
    root, locks = estate
    lock = locks / "parse_custbill.lock"
    lock.write_bytes(b"stale")
    (root / "incoming/CUSTBILL_a.dat").write_bytes(b"X\n")
    proc = run(estate)
    assert (proc.returncode, proc.stderr) == (0, b"")
    assert proc.stdout == WARNING + START + parsed_line(b"CUSTBILL_a", 1) + END
    assert lock.read_bytes() == b"stale"
    assert (root / "incoming/CUSTBILL_a.dat.done").is_file()


def test_lock_touch_errors_are_swallowed(estate):
    root, locks = estate
    proc = run((root, locks / "absent"))
    assert (proc.returncode, proc.stdout, proc.stderr) == (0, START + END, b"")
    assert not (locks / "absent").exists()


def test_nonmatching_names_and_nonregular_matches_are_left_alone(estate):
    root, _ = estate
    incoming = root / "incoming"
    for name in ("custbill.dat", "CUSTBILL.dat.done", "OTHER.dat", "CUSTBILL.dat.bak"):
        (incoming / name).write_bytes(b"untouched")
    (incoming / "CUSTBILL_directory.dat").mkdir()
    (incoming / "CUSTBILL_broken.dat").symlink_to("missing")
    before = {p.relative_to(root) for p in root.rglob("*")}
    proc = run(estate)
    assert (proc.returncode, proc.stdout, proc.stderr) == (0, START + END, b"")
    assert {p.relative_to(root) for p in root.rglob("*")} == before | {Path("parsed")}
    assert (incoming / "CUSTBILL_broken.dat").is_symlink()
    assert all(p.read_bytes() == b"untouched" for p in incoming.iterdir() if p.is_file())


@pytest.mark.parametrize("amount,expected", [
    (b"junk", b"0.00"), (b"-123abc", b"-1.23"), (b"+123.5tail", b"1.24"),
    (b"  .5x", b"0.01"), (b"1e3foo", b"10.00"), (b"1e+oops", b"0.01"),
    (b"0x10", b"0.00"), (b"0x1.fp2", b"0.00"), (b"08", b"0.08"),
    (b"inf", b"0.00"), (b"-inf", b"-inf"), (b"+inf", b"+inf"),
    (b"nan", b"0.00"), (b"-nan", b"-nan"), (b"+nan", b"+nan"),
    (b"1e999", b"+inf"), (b"-0", b"0.00"), (b"-0.1", b"-0.00"),
    (b"125.5", b"1.25"), (b"101.5", b"1.01"), (b"1\t2", b"0.01"),
    (b"\v-30", b"-0.30"), (b"-1e-999", b"0.00"),
])
def test_awk_numeric_prefix_and_float_rounding(amount, expected):
    assert parser._parse(record(amount) + b"\n") == b"ID|NAME|2026-01-15|" + expected + b"|USD|01\n"


@pytest.mark.parametrize("data,expected", [
    (b"", b""), (b"HDRonly\nTRL0000000000\n", b""),
    (b"\nX\n", b"||--|0.00||\nX||--|0.00||\n"),
    (b"SHORT\r\n", b"SHORT\r||--|0.00||\n"),
    (record(), b"ID|NAME|2026-01-15|1234.56|USD|01\n"),
    (record(name=b"\xff\xc3\xa9") + b"\n", b"ID|\xff\xc3\xa9|2026-01-15|1234.56|USD|01\n"),
    (record(customer=b" ID\t", name=b" NAME\t", date=b"abcd", ccy=b"\t  ", rt=b"  ") + b"extra\r\n",
     b" ID\t| NAME\t|abcd-  -  |1234.56|\t|  \n"),
    (record(customer=b"X|Y", date=b"12345678") + b"\n",
     b"X|Y|NAME-  -  |123456.78|000000123456|USD|01\n"),
])
def test_byte_columns_trimming_malformed_dates_and_unescaped_pipes(data, expected):
    assert parser._parse(data) == expected


@pytest.mark.parametrize("trailer,expected", [
    (b"", b"?"), (b"TRL0000000000\n", b"?"),
    (b"TRL0000009999\n", b"9999"), (b"TRLabc\n", b"abc"),
    (b"TRL0000000000\nTRL0000000002suffix\nTRL0000000000\nTRL0000000003", b"\n2\n\n3"),
])
def test_trailers_are_printed_not_reconciled_and_header_trailer_prefixes_are_removed(estate, trailer, expected):
    root, _ = estate
    data = b"HDRany prefix\nX\n" + trailer
    source = root / "incoming/CUSTBILL_a.dat"
    source.write_bytes(data)
    proc = run(estate)
    assert (proc.returncode, proc.stderr) == (0, b"")
    assert proc.stdout == START + parsed_line(b"CUSTBILL_a", 1, expected) + END
    assert (root / "parsed/CUSTBILL_a.psv").read_bytes() == b"X||--|0.00||\n"
    assert not source.exists()
    assert source.with_name(source.name + ".done").read_bytes() == data


def test_glob_byte_order_overwrite_and_rerun(estate):
    root, _ = estate
    names = ["CUSTBILL_z", "CUSTBILL_\u00e9", "CUSTBILL_Z", "CUSTBILL_A"]
    for name in names:
        (root / f"incoming/{name}.dat").write_bytes(b"X\n")
        (root / f"incoming/{name}.dat.done").write_bytes(b"old input")
    (root / "parsed").mkdir()
    (root / "parsed/CUSTBILL_A.psv").write_bytes(b"old report")
    proc = run(estate)
    expected_lines = b"".join(parsed_line(n.encode(), 1) for n in sorted(names, key=lambda n: n.encode()))
    assert (proc.returncode, proc.stdout, proc.stderr) == (0, START + expected_lines + END, b"")
    for name in names:
        assert (root / f"parsed/{name}.psv").read_bytes() == b"X||--|0.00||\n"
        assert (root / f"incoming/{name}.dat.done").read_bytes() == b"X\n"
    before = golden_replay.manifest(root)
    again = run(estate)
    assert (again.returncode, again.stdout, again.stderr) == (0, WARNING + START + END, b"")
    assert golden_replay.manifest(root) == before


def test_symlink_input_is_read_but_only_the_link_is_renamed(estate):
    root, _ = estate
    target = root / "original"
    target.write_bytes(b"X\n")
    source = root / "incoming/CUSTBILL_link.dat"
    source.symlink_to(target)
    proc = run(estate)
    assert (proc.returncode, proc.stderr) == (0, b"")
    assert (root / "incoming/CUSTBILL_link.dat.done").is_symlink()
    assert target.read_bytes() == b"X\n"


def test_done_directory_receives_input(estate):
    root, _ = estate
    source = root / "incoming/CUSTBILL_a.dat"
    source.write_bytes(b"X\n")
    done = root / "incoming/CUSTBILL_a.dat.done"
    done.mkdir()
    (done / source.name).write_bytes(b"old input")
    proc = run(estate)
    assert (proc.returncode, proc.stderr) == (0, b"")
    assert not source.exists()
    assert (done / source.name).read_bytes() == b"X\n"


def test_move_failure_is_swallowed(estate):
    root, _ = estate
    source = root / "incoming/CUSTBILL_a.dat"
    source.write_bytes(b"X\n")
    (root / "incoming/CUSTBILL_a.dat.done/CUSTBILL_a.dat").mkdir(parents=True)
    proc = run(estate)
    assert (proc.returncode, proc.stderr) == (0, b"")
    assert source.read_bytes() == b"X\n"
    assert (root / "parsed/CUSTBILL_a.psv").read_bytes() == b"X||--|0.00||\n"


@pytest.mark.parametrize("blocked", ["directory", "parent"])
def test_output_failure_still_moves_input_and_exits_zero(estate, blocked):
    root, _ = estate
    source = root / "incoming/CUSTBILL_a.dat"
    source.write_bytes(b"X\nTRL0000000001\n")
    out = root / "parsed/CUSTBILL_a.psv"
    if blocked == "directory":
        out.mkdir(parents=True)
        count, error = 0, "Is a directory"
    else:
        out.parent.write_bytes(b"not a directory")
        count, error = "", "Not a directory"
    proc = run(estate)
    assert (proc.returncode, proc.stdout) == (0, START + parsed_line(b"CUSTBILL_a", count, b"1") + END)
    assert proc.stderr == f"{parser._LEGACY_SCRIPT}: line 59: {out}: {error}\n".encode()
    assert not source.exists()
    assert (root / "incoming/CUSTBILL_a.dat.done").is_file()


def test_nul_bytes_keep_grep_binary_count_and_trailer_warning(estate):
    root, _ = estate
    source = root / "incoming/CUSTBILL_a.dat"
    source.write_bytes(b"ID\x00X\nTRL0000000002\n")
    proc = run(estate)
    assert (proc.returncode, proc.stdout) == (0, START + parsed_line(b"CUSTBILL_a", 2) + END)
    assert proc.stderr == f"grep: {source}: binary file matches\n".encode()
    assert (root / "parsed/CUSTBILL_a.psv").read_bytes() == b"ID\x00X||--|0.00||\n"


def test_clock_is_read_for_each_log_line(monkeypatch, capsys):
    times = iter([1.0, 2.0, 3.0])
    monkeypatch.setattr(parser.cc, "now_epoch", lambda: next(times))
    monkeypatch.setattr(parser.cc, "date_cmd_stamp", lambda epoch: str(epoch))
    for text in ("start", "parsed", "done"):
        parser._log(text)
    assert capsys.readouterr().out == "1.0 start\n2.0 parsed\n3.0 done\n"


def test_unquoted_filename_with_spaces_keeps_legacy_partial_failure(estate):
    root, _ = estate
    source = root / "incoming/CUSTBILL has spaces.dat"
    source.write_bytes(b"X\n")
    proc = run(estate)
    assert (proc.returncode, proc.stdout) == (0, START + parsed_line(b"", 0) + END)
    assert proc.stderr == (
        b"basename: extra operand 'spaces.dat'\nTry 'basename --help' for more information.\n"
        + f"grep: {root}/incoming/CUSTBILL: No such file or directory\n".encode()
        + b"grep: has: No such file or directory\ngrep: spaces.dat: No such file or directory\n"
    )
    assert source.read_bytes() == b"X\n"
    assert (root / "parsed/.psv").read_bytes() == b""


def test_failed_input_read_produces_empty_output_and_trailer_error(estate, monkeypatch, capsys):
    root, locks = estate
    source = root / "incoming/CUSTBILL_a.dat"
    source.write_bytes(b"X\n")
    read_bytes = Path.read_bytes

    def fail_read(path):
        if path == source:
            raise PermissionError(13, "Permission denied")
        return read_bytes(path)

    monkeypatch.setenv("OTTERWORKS_LEGACY_ROOT", str(root))
    monkeypatch.setenv("CUSTBILL_LOCK_DIR", str(locks))
    monkeypatch.setattr(Path, "read_bytes", fail_read)
    assert parser.main() == 0
    output = capsys.readouterr()
    assert "0 records (trailer says ?)" in output.out
    assert output.err == f"grep: {source}: Permission denied\n"
    assert (root / "parsed/CUSTBILL_a.psv").read_bytes() == b""
    assert (root / "incoming/CUSTBILL_a.dat.done").is_file()
