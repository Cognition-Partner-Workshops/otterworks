import errno
from pathlib import Path

import pytest

import custbill_common as cc
import golden_replay
import sftp_ingest_poll as job

STAMP = "Thu Jan 15 00:00:00 UTC 2026"
SUFFIX = ".20260115000000"
WARNING = "lock file present, another ingest may be running, continuing anyway\n"


@pytest.mark.parametrize("ns", golden_replay.golden_namespaces("sftp_ingest_poll"))
def test_golden_replay(ns, tmp_path):
    expected, actual = golden_replay.replay("sftp_ingest_poll", ns, tmp_path)
    golden_replay.assert_matches(expected, actual)


def test_both_golden_namespaces_are_present():
    assert {"dev", "qa"} <= set(golden_replay.golden_namespaces("sftp_ingest_poll"))


@pytest.fixture
def run_env(tmp_path, monkeypatch):
    root = tmp_path / "root"
    locks = tmp_path / "locks"
    locks.mkdir()
    monkeypatch.setenv("OTTERWORKS_LEGACY_ROOT", str(root))
    monkeypatch.setenv("CUSTBILL_LOCK_DIR", str(locks))
    monkeypatch.setenv("CUSTBILL_NOW", golden_replay.GOLDEN_NOW)
    monkeypatch.setenv("TZ", "UTC")
    job.time.tzset()
    monkeypatch.setattr(cc, "host_profile", lambda: "dev")
    sleeps = []
    monkeypatch.setattr(job.time, "sleep", sleeps.append)
    return root, locks, sleeps


def seed(root, name="CUSTBILL_EDGE.dat", data=b"a\x00b\xff\r\n"):
    drop = root / "sftp-drop" / "upload"
    drop.mkdir(parents=True, exist_ok=True)
    path = drop / name
    path.write_bytes(data)
    return path


def output(root, *lines):
    return "\n".join([
        f"{STAMP} sftp_ingest_poll starting, drop={root}/sftp-drop/upload",
        *lines,
        f"{STAMP} sftp_ingest_poll done",
        "",
    ])


def test_fresh_root_creates_only_expected_directories_and_lock(run_env, capsys):
    root, locks, sleeps = run_env
    assert job.main() == 0
    assert capsys.readouterr() == (output(root), "")
    assert sleeps == [2, 2]
    assert (locks / "sftp_ingest.lock").is_file()
    assert {p.relative_to(root).as_posix() for p in root.rglob("*")} == {
        "incoming", "archive", "sftp-drop", "sftp-drop/upload",
    }


def test_existing_lock_warns_run_continues_and_rerun_keeps_lock(run_env, capsys):
    root, locks, sleeps = run_env
    lock = locks / "sftp_ingest.lock"
    lock.write_bytes(b"old lock contents")
    source = seed(root)
    data = source.read_bytes()
    assert job.main() == 0
    assert capsys.readouterr() == (
        WARNING + output(root, f"{STAMP} ingested {source.name} ({len(data)} bytes)"), "",
    )
    assert lock.read_bytes() == b"old lock contents"
    assert (root / "incoming" / source.name).read_bytes() == data
    assert job.main() == 0
    assert capsys.readouterr() == (WARNING + output(root), "")
    assert lock.exists()
    assert sleeps == [1, 2, 2, 2, 2]


def test_nonmatching_names_directories_and_dangling_symlinks_are_untouched(run_env, capsys):
    root, _, sleeps = run_env
    for name in ("custbill_lower.dat", "CUSTBILL_UPPER.DAT", "CUSTBILL.dat.tmp", ".CUSTBILL.dat"):
        seed(root, name)
    drop = root / "sftp-drop" / "upload"
    (drop / "CUSTBILL_DIR.dat").mkdir()
    (drop / "CUSTBILL_DANGLING.dat").symlink_to(drop / "missing")
    before = sorted(p.name for p in drop.iterdir())
    assert job.main() == 0
    assert sorted(p.name for p in drop.iterdir()) == before
    assert sleeps == [2, 2]
    assert capsys.readouterr() == (output(root), "")


def test_c_byte_order_binary_empty_files_and_existing_copies_are_overwritten(run_env, capsys):
    root, _, sleeps = run_env
    names = ["CUSTBILL_é.dat", "CUSTBILL_z.dat", "CUSTBILL_A.dat", "CUSTBILL.dat"]
    data = {name: bytes([i, 255]) if i else b"" for i, name in enumerate(names)}
    for name in names:
        seed(root, name, data[name])
        for directory, suffix in (("incoming", ""), ("archive", SUFFIX)):
            target = root / directory
            target.mkdir(exist_ok=True)
            (target / (name + suffix)).write_bytes(b"stale and longer contents")
    assert job.main() == 0
    lines = [f"{STAMP} ingested {name} ({len(data[name])} bytes)"
             for name in sorted(names, key=lambda n: n.encode())]
    assert capsys.readouterr() == (output(root, *lines), "")
    assert sleeps == [1, 1, 1, 1, 2, 2]
    assert not list((root / "sftp-drop" / "upload").iterdir())
    for name in names:
        assert (root / "incoming" / name).read_bytes() == data[name]
        assert (root / "archive" / (name + SUFFIX)).read_bytes() == data[name]


def test_source_symlink_is_followed_then_only_link_is_deleted(run_env, capsys):
    root, _, _ = run_env
    target = seed(root, "other.txt", b"target contents")
    link = target.parent / "CUSTBILL_LINK.dat"
    link.symlink_to(target)
    assert job.main() == 0
    assert not link.exists()
    assert target.read_bytes() == b"target contents"
    assert (root / "incoming" / link.name).read_bytes() == target.read_bytes()
    assert (root / "archive" / (link.name + SUFFIX)).read_bytes() == target.read_bytes()
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize("growing_passes", [1, 2, 3])
def test_growing_file_retried_each_pass_or_left_in_drop(run_env, monkeypatch, capsys, growing_passes):
    root, _, sleeps = run_env
    source = seed(root, data=b"a")
    settles = 0

    def sleep(seconds):
        nonlocal settles
        sleeps.append(seconds)
        if seconds == 1:
            settles += 1
            if settles <= growing_passes:
                with source.open("ab") as stream:
                    stream.write(b"b")

    monkeypatch.setattr(job.time, "sleep", sleep)
    assert job.main() == 0
    lines = [f"{STAMP} {source.name} still growing, skipping this pass"] * growing_passes
    if growing_passes < 3:
        lines.append(f"{STAMP} ingested {source.name} ({1 + growing_passes} bytes)")
        assert not source.exists()
        assert (root / "incoming" / source.name).read_bytes() == b"a" + b"b" * growing_passes
    else:
        assert source.read_bytes() == b"abbb"
        assert not list((root / "incoming").iterdir())
        assert not list((root / "archive").iterdir())
    assert capsys.readouterr() == (output(root, *lines), "")
    assert sleeps == ([1, 2, 1, 2] if growing_passes == 1 else [1, 2, 1, 2, 1])


def test_new_arrival_on_last_pass_and_same_size_rewrite(run_env, monkeypatch, capsys):
    root, _, sleeps = run_env
    arrival = None

    def sleep(seconds):
        nonlocal arrival
        sleeps.append(seconds)
        if sleeps == [2, 2]:
            arrival = seed(root, data=b"old")
        elif seconds == 1:
            arrival.write_bytes(b"new")

    monkeypatch.setattr(job.time, "sleep", sleep)
    assert job.main() == 0
    assert sleeps == [2, 2, 1]
    assert (root / "incoming" / arrival.name).read_bytes() == b"new"
    assert capsys.readouterr() == (output(root, f"{STAMP} ingested {arrival.name} (3 bytes)"), "")


@pytest.mark.parametrize("blocked", ["incoming", "archive"])
def test_copy_failure_does_not_prevent_other_copy_or_deletion(run_env, capsys, blocked):
    root, _, _ = run_env
    source = seed(root)
    data = source.read_bytes()
    (root / blocked).write_bytes(b"not a directory")
    assert job.main() == 0
    captured = capsys.readouterr()
    count = "" if blocked == "incoming" else str(len(data))
    assert captured.out == output(root, f"{STAMP} ingested {source.name} ({count} bytes)")
    if blocked == "incoming":
        legacy = golden_replay.PYJOBS.parent / "jobs" / "sftp_ingest_poll.ksh"
        assert captured.err == f"{legacy}[61]: {root}/incoming/{source.name}: cannot open [Not a directory]\n"
        assert (root / "archive" / (source.name + SUFFIX)).read_bytes() == data
    else:
        assert captured.err == ""
        assert (root / "incoming" / source.name).read_bytes() == data
    assert not source.exists()


def test_failed_overwrite_reports_stale_incoming_bytes(run_env, monkeypatch, capsys):
    root, _, _ = run_env
    source = seed(root)
    incoming = root / "incoming"
    incoming.mkdir()
    (incoming / source.name).write_bytes(b"old")
    original = job.shutil.copyfile

    def copy(src, dst):
        if dst.parent == incoming:
            raise PermissionError(errno.EACCES, "Permission denied")
        return original(src, dst)

    monkeypatch.setattr(job.shutil, "copyfile", copy)
    assert job.main() == 0
    assert not source.exists()
    assert capsys.readouterr() == (output(root, f"{STAMP} ingested {source.name} (3 bytes)"), "")


def test_rm_failure_is_silent_and_file_is_reprocessed_three_times(run_env, monkeypatch, capsys):
    root, _, sleeps = run_env
    source = seed(root)

    def unlink(path, *args, **kwargs):
        raise PermissionError(errno.EACCES, "Permission denied")

    monkeypatch.setattr(Path, "unlink", unlink)
    assert job.main() == 0
    assert source.exists()
    line = f"{STAMP} ingested {source.name} ({source.stat().st_size} bytes)"
    assert capsys.readouterr() == (output(root, line, line, line), "")
    assert sleeps == [1, 2, 1, 2, 1]
    assert len(list((root / "archive").iterdir())) == 1


def test_mkdir_and_lock_touch_failures_are_swallowed(run_env, monkeypatch, capsys):
    root, locks, sleeps = run_env
    root.write_bytes(b"not a directory")
    monkeypatch.setenv("CUSTBILL_LOCK_DIR", str(locks / "missing"))
    assert job.main() == 0
    assert capsys.readouterr() == (output(root), "")
    assert sleeps == [2, 2]
    assert not list(locks.iterdir())


def test_inaccessible_file_and_lock_checks_are_silent(run_env, monkeypatch, capsys):
    root, _, sleeps = run_env
    source = seed(root)

    def is_file(path):
        raise PermissionError(errno.EACCES, "Permission denied")

    monkeypatch.setattr(Path, "is_file", is_file)
    assert job.main() == 0
    assert source.exists()
    assert capsys.readouterr() == (output(root), "")
    assert sleeps == [2, 2]


def test_unquoted_filename_spaces_leave_input_and_report_truncated_basename(run_env, capsys):
    root, _, sleeps = run_env
    source = seed(root, "CUSTBILL_TWO WORDS.dat", b"abc")
    assert job.main() == 0
    assert source.read_bytes() == b"abc"
    legacy = golden_replay.PYJOBS.parent / "jobs" / "sftp_ingest_poll.ksh"
    error = f"{legacy}[61]: {root}/incoming/CUSTBILL_TWO: cannot open [No such file or directory]\n"
    line = f"{STAMP} ingested CUSTBILL_TWO ( bytes)"
    assert capsys.readouterr() == (output(root, line, line, line), error * 3)
    assert sleeps == [1, 2, 1, 2, 1]


def test_incoming_directory_copies_inside_but_wc_reports_zero(run_env, capsys):
    root, _, _ = run_env
    source = seed(root, data=b"abc")
    destination = root / "incoming" / source.name
    destination.mkdir(parents=True)
    assert job.main() == 0
    assert (destination / source.name).read_bytes() == b"abc"
    assert capsys.readouterr() == (
        output(root, f"{STAMP} ingested {source.name} (0 bytes)"),
        "wc: 'standard input': Is a directory\n",
    )


def test_disappearing_during_settle_prints_redirection_error_then_skip(run_env, monkeypatch, capsys):
    root, _, sleeps = run_env
    source = seed(root)

    def sleep(seconds):
        sleeps.append(seconds)
        if seconds == 1:
            source.unlink()

    monkeypatch.setattr(job.time, "sleep", sleep)
    assert job.main() == 0
    legacy = golden_replay.PYJOBS.parent / "jobs" / "sftp_ingest_poll.ksh"
    assert capsys.readouterr() == (
        output(root, f"{STAMP} {source.name} still growing, skipping this pass"),
        f"{legacy}[53]: {source}: cannot open [No such file or directory]\n",
    )
    assert sleeps == [1, 2, 2]


@pytest.mark.parametrize("profile,root,drop", [
    ("prod", "/data/otterworks", "/sftp/mainframe/upload"),
    ("uat", "/data2/otterworks_uat", "/sftp_uat/mainframe/upload"),
    ("dev", "/tmp/otterworks-legacy", "/tmp/otterworks-legacy/sftp-drop/upload"),
])
def test_hostname_roots_and_drop_branches(profile, root, drop):
    resolved_root = cc.legacy_root(profile, {})
    assert resolved_root == Path(root)
    assert job.drop_directory(profile, resolved_root) == Path(drop)


def test_all_clock_reads_use_shared_frozen_clock(run_env, monkeypatch, capsys):
    root, _, _ = run_env
    source = seed(root)
    epoch = cc.now_epoch()
    epochs = iter([epoch, epoch + 60, epoch + 120, epoch + 180])
    monkeypatch.setattr(cc, "now_epoch", lambda: next(epochs))
    assert job.main() == 0
    assert (root / "archive" / (source.name + ".20260115000100")).is_file()
    assert capsys.readouterr() == (
        f"{STAMP} sftp_ingest_poll starting, drop={root}/sftp-drop/upload\n"
        f"Thu Jan 15 00:02:00 UTC 2026 ingested {source.name} (6 bytes)\n"
        "Thu Jan 15 00:03:00 UTC 2026 sftp_ingest_poll done\n", "",
    )
