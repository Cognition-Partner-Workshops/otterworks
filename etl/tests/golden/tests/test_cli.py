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
