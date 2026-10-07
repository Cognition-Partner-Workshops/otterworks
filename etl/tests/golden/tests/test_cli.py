import dataclasses

import pytest

from harness import cli, scenario, settings


def test_write_files_replaces_stale_snapshot_files(tmp_path):
    (tmp_path / "old.json").write_text("{}")
    cli.write_files(tmp_path / "snap", {"a.json": "1\n"})
    cli.write_files(tmp_path / "snap", {"b.json": "2\n"})
    assert sorted(p.name for p in (tmp_path / "snap").iterdir()) == ["b.json"]
    assert (tmp_path / "old.json").exists()


def test_report_diff_keeps_the_diff_next_to_the_run_logs(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(settings, "RUNS_DIR", tmp_path)
    scn = scenario.discover("analytics_daily", "smoke")[0]
    (tmp_path / scn.script / scn.name).mkdir(parents=True)
    lines = cli.diff({"s3.json": "a\n"}, {"s3.json": "b\n"})
    cli.report_diff(scn, lines)
    saved = (tmp_path / scn.script / scn.name / cli.DIFF_FILE).read_text()
    assert saved == capsys.readouterr().out == "".join(lines)
    assert "-a\n" in saved and "+b\n" in saved


def _retire_everything(tmp_path, monkeypatch):
    """A tree where etl/scripts/ and etl/run.sh are gone (every script retired)."""
    (tmp_path / "etl" / "scripts").mkdir(parents=True)
    monkeypatch.setattr(settings, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(settings, "ETL_DIR", tmp_path / "etl")


def test_check_mode_keeps_working_once_a_script_is_retired(tmp_path, monkeypatch):
    _retire_everything(tmp_path, monkeypatch)

    def no_infra(*_args, **_kwargs):
        raise AssertionError("check of a retired script must not touch infra or docker")

    for module, name in [
        (cli.infra, "wait_ready"),
        (cli.infra, "reset"),
        (cli.runner, "ensure_image"),
        (cli.runner, "run"),
    ]:
        monkeypatch.setattr(module, name, no_infra)
    scn = scenario.discover("analytics_daily", "smoke")[0]
    ok, detail = cli.execute(scn, None, "check")
    assert ok and detail.startswith("SKIP legacy run: script retired")
    assert cli.main(["--script", "all", "--mode", "check"]) == 0


def test_retired_script_with_a_broken_golden_fails_check(tmp_path, monkeypatch):
    _retire_everything(tmp_path, monkeypatch)
    golden = tmp_path / "smoke" / "golden"
    golden.mkdir(parents=True)
    (golden / "s3.json").write_text("{not json")
    scn = dataclasses.replace(
        scenario.discover("analytics_daily", "smoke")[0], path=tmp_path / "smoke"
    )
    ok, detail = cli.execute(scn, None, "check")
    assert not ok and "not valid JSON" in detail
    scn = dataclasses.replace(scn, path=tmp_path / "empty")
    assert cli.execute(scn, None, "check") == (
        False,
        "script retired and no golden recorded",
    )


@pytest.mark.parametrize("mode", ["record", "repeat"])
def test_record_and_repeat_need_the_script_back_from_git(tmp_path, monkeypatch, mode):
    _retire_everything(tmp_path, monkeypatch)
    scn = scenario.discover("analytics_daily", "smoke")[0]
    with pytest.raises(cli.HarnessError) as exc:
        cli.execute(scn, "img:tag", mode)
    message = str(exc.value)
    assert "etl/scripts/analytics_daily.py and etl/run.sh are retired" in message
    assert "restore it from git history" in message


def test_restored_script_without_run_sh_is_refused(tmp_path, monkeypatch):
    _retire_everything(tmp_path, monkeypatch)
    (tmp_path / "etl" / "scripts" / "analytics_daily.py").write_text("")
    scn = scenario.discover("analytics_daily", "smoke")[0]
    with pytest.raises(cli.HarnessError, match=r"but etl/run.sh is retired"):
        cli.execute(scn, "img:tag", "check")


def test_record_of_a_retired_script_stops_before_infra(tmp_path, monkeypatch, capsys):
    _retire_everything(tmp_path, monkeypatch)

    def no_infra(*_args, **_kwargs):
        raise AssertionError("must refuse before touching infra or docker")

    monkeypatch.setattr(cli.infra, "wait_ready", no_infra)
    monkeypatch.setattr(cli.runner, "ensure_image", no_infra)
    assert cli.main(["--script", "analytics_daily", "--mode", "record"]) == 2
    assert "restore it from git history" in capsys.readouterr().err
