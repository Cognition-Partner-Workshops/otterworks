from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from migration.snowflake.gate import cutover
from migration.snowflake.target.tasks import tasks as task_manager

RUN = "sfm-20261013-lv"
PREFIX = "OW_UBW_SFM_20261013_LV"


def run_cutover(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    return_codes: tuple[int, ...],
) -> list[list[str]]:
    gate_dir = tmp_path / "migration" / "snowflake" / "gate"
    output_dir = gate_dir / "out"
    output_dir.mkdir(parents=True)
    (output_dir / "ledger.json").write_text('{"date": "2026-09-30"}', encoding="utf-8")
    monkeypatch.setattr(cutover, "HERE", gate_dir)
    monkeypatch.setattr(cutover, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["cutover.py", "--run", RUN])

    calls: list[list[str]] = []
    codes = iter(return_codes)

    def fake_run(command: list[str], *, cwd: Path, check: bool) -> SimpleNamespace:
        assert cwd == tmp_path
        assert check is False
        calls.append(command)
        return SimpleNamespace(returncode=next(codes))

    monkeypatch.setattr(cutover.subprocess, "run", fake_run)
    assert cutover.main() == return_codes[-1]
    return calls


def test_cutover_resumes_task_graph_after_passing_reread(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = run_cutover(tmp_path, monkeypatch, (0, 0))

    assert len(calls) == 2
    assert calls[0][-1] == "--reread"
    assert calls[1] == [
        sys.executable,
        str(tmp_path / "migration" / "snowflake" / "target" / "tasks" / "tasks.py"),
        "--run",
        RUN,
        "resume",
    ]


def test_cutover_does_not_resume_when_reread_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = run_cutover(tmp_path, monkeypatch, (7,))

    assert len(calls) == 1
    assert calls[0][-1] == "--reread"


def test_cutover_returns_nonzero_when_resume_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = run_cutover(tmp_path, monkeypatch, (0, 5))

    assert len(calls) == 2
    assert calls[1][-1] == "resume"


class FakeCursor:
    description = (("created_on",), ("name",))

    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple[str, ...] | None]] = []

    def __enter__(self) -> FakeCursor:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def execute(self, statement: str, parameters: tuple[str, ...] | None = None) -> None:
        self.executed.append((statement, parameters))

    def fetchall(self) -> list[tuple[None, str]]:
        return [
            (None, "UBW_WEEKLY_RETENTION"),
            (None, "UBW_MONTHLY_OVERAGE"),
        ]


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self.fake_cursor = cursor

    def __enter__(self) -> FakeConnection:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def cursor(self) -> FakeCursor:
        return self.fake_cursor


def test_resume_skips_absent_standalone_tasks_and_enables_root(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    cursor = FakeCursor()
    monkeypatch.setattr(
        task_manager, "dbt_connection", lambda run: FakeConnection(cursor)
    )

    task_manager.manage(RUN, "resume")

    assert cursor.executed == [
        (f"SHOW TASKS IN SCHEMA {PREFIX}.OPS", None),
        (f"ALTER TASK {PREFIX}.OPS.UBW_WEEKLY_RETENTION RESUME", None),
        (f"ALTER TASK {PREFIX}.OPS.UBW_MONTHLY_OVERAGE RESUME", None),
        (
            "SELECT SYSTEM$TASK_DEPENDENTS_ENABLE(%s)",
            (f"{PREFIX}.OPS.UBW_NIGHTLY_LOAD",),
        ),
    ]
    output = capsys.readouterr().out
    assert f"ABSENT            {PREFIX}.OPS.UBW_HOURLY_AUDIT" in output
    assert f"ABSENT            {PREFIX}.OPS.UBW_WEEKLY_CAPACITY_FORECAST" in output
