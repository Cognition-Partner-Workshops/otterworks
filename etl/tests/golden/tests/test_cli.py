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
    lines = cli.diff({"s3.json": "a\n"}, {"s3.json": "b\n"})
    cli.report_diff(scn, "check", lines)
    saved = (tmp_path / scn.script / scn.name / "check" / cli.DIFF_FILE).read_text()
    assert saved == capsys.readouterr().out == "".join(lines)
    assert "-a\n" in saved and "+b\n" in saved


def test_modes_keep_separate_diffs_and_snapshots(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(settings, "RUNS_DIR", tmp_path)
    scn = scenario.discover("analytics_daily", "smoke")[0]
    assert cli.mode_dir(scn, "check") != cli.mode_dir(scn, "repeat")
    cli.report_diff(scn, "check", cli.diff({"r.json": "1\n"}, {"r.json": "0\n"}))
    cli.write_files(cli.mode_dir(scn, "check") / "snapshot-1", {"r.json": "0\n"})
    cli.write_files(cli.mode_dir(scn, "repeat") / "snapshot-1", {"r.json": "0\n"})
    assert (cli.mode_dir(scn, "check") / cli.DIFF_FILE).exists()
    assert (cli.mode_dir(scn, "check") / "snapshot-1" / "r.json").exists()
