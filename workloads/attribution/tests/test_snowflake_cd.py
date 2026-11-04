import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "snowflake"))
import cd  # noqa: E402
import git_utils  # noqa: E402


def test_merge_provenance_adds_redeploys_drops_and_preserves_excluded_types():
    provenance = {
        "source": {"commit": "a" * 40},
        "deployed_objects": [
            {
                "type": "table",
                "name": "DB.ANALYTICS.OLD",
                "state": "deployed",
                "deployed_at": "2026-01-01T00:00:00Z",
                "deployed_commit": "a" * 40,
            },
            {
                "type": "table",
                "name": "DB.ANALYTICS.CURRENT",
                "state": "deployed",
                "deployed_at": "2026-01-01T00:00:00Z",
                "deployed_commit": "a" * 40,
            },
            {
                "type": "resource_monitor",
                "name": "DB_MONITOR",
                "state": "deployed",
                "deployed_at": "2026-01-01T00:00:00Z",
                "deployed_commit": "a" * 40,
            },
        ],
    }
    inventory = [
        {"type": "table", "name": "DB.ANALYTICS.CURRENT"},
        {"type": "database", "name": "DB", "devin_csid": "cs_example"},
        {"type": "unsupported", "name": "IGNORED"},
    ]

    updated, warnings = cd.merge_provenance(
        provenance,
        inventory,
        {("table", "DB.ANALYTICS.CURRENT")},
        commit="b" * 40,
        deployed_at="2026-02-01T00:00:00Z",
    )
    by_key = {(item["type"], item["name"]): item for item in updated["deployed_objects"]}

    assert updated["source"]["commit"] == "b" * 40
    assert by_key[("table", "DB.ANALYTICS.CURRENT")]["deployed_commit"] == "b" * 40
    assert by_key[("table", "DB.ANALYTICS.OLD")]["state"] == "dropped"
    assert by_key[("database", "DB")]["devin_csid"] == "cs_example"
    assert by_key[("resource_monitor", "DB_MONITOR")]["deployed_commit"] == "a" * 40
    assert not any(kind == "unsupported" for kind, _ in by_key)
    assert warnings == ["Previously deployed object is absent from Snowflake: table DB.ANALYTICS.OLD"]


def test_rollback_target_returns_first_different_source_commit(monkeypatch):
    def fake_run(command, **kwargs):
        if "rev-parse" in command:
            return subprocess.CompletedProcess(command, 0, stdout="false\n", stderr="")
        if "log" in command:
            return subprocess.CompletedProcess(command, 0, stdout="new\nold\n", stderr="")
        commit = command[command.index("show") + 1].split(":", 1)[0]
        source = "b" * 40 if commit == "new" else "a" * 40
        document = yaml.safe_dump({"source": {"commit": source}})
        return subprocess.CompletedProcess(command, 0, stdout=document, stderr="")

    monkeypatch.setattr(cd.subprocess, "run", fake_run)
    assert cd.rollback_target("b" * 40, repo="/repo") == "a" * 40


def test_prepare_run_environment_prefers_sfnfr_credentials(monkeypatch):
    env = os.environ.copy()
    env.update(
        SFNFR_ACCOUNT="target-account",
        SNOWFLAKE_ACCOUNT="stale-account",
        SFNFR_USER="target-user",
        SNOWFLAKE_USER="stale-user",
        SFNFR_ROLE="target-role",
        SNOWFLAKE_ROLE="stale-role",
    )
    monkeypatch.setattr(cd.os, "environ", env)

    prepared, _ = cd.prepare_run_environment("a" * 40)

    assert prepared["SNOWFLAKE_ACCOUNT"] == "target-account"
    assert prepared["SNOWFLAKE_USER"] == "target-user"
    assert prepared["SNOWFLAKE_ROLE"] == "target-role"


def test_pushed_commit_guard_accepts_ancestor_of_remote_branch(monkeypatch):
    pushed = "f" * 40

    def fake_run(command, **kwargs):
        if command[3:5] == ["ls-remote", "--heads"]:
            output = f"{pushed}\trefs/heads/demo-stack-snowflake\n"
            return subprocess.CompletedProcess(command, 0, stdout=output, stderr="")
        if command[3:5] == ["branch", "--show-current"]:
            return subprocess.CompletedProcess(command, 0, stdout="demo-stack-snowflake\n", stderr="")
        if "rev-parse" in command:
            return subprocess.CompletedProcess(command, 0, stdout=f"{pushed}\n", stderr="")
        if "merge-base" in command:
            assert command[-2:] == ["a" * 40, "refs/remotes/origin/demo-stack-snowflake"]
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        raise AssertionError(command)

    monkeypatch.setattr(git_utils.subprocess, "run", fake_run)
    assert git_utils.require_pushed_commit("a" * 40, "/repo") == "refs/remotes/origin/demo-stack-snowflake"


def test_pushed_commit_guard_rejects_unpushed_commit(monkeypatch):
    pushed = "f" * 40

    def fake_run(command, **kwargs):
        if command[3:5] == ["ls-remote", "--heads"]:
            output = f"{pushed}\trefs/heads/demo-stack-snowflake\n"
            return subprocess.CompletedProcess(command, 0, stdout=output, stderr="")
        if command[3:5] == ["branch", "--show-current"]:
            return subprocess.CompletedProcess(command, 0, stdout="demo-stack-snowflake\n", stderr="")
        if "rev-parse" in command:
            return subprocess.CompletedProcess(command, 0, stdout=f"{pushed}\n", stderr="")
        if "merge-base" in command:
            return subprocess.CompletedProcess(command, 1, stdout="", stderr="")
        raise AssertionError(command)

    monkeypatch.setattr(git_utils.subprocess, "run", fake_run)
    with pytest.raises(ValueError, match="not an ancestor"):
        git_utils.require_pushed_commit("a" * 40, "/repo")


def test_pushed_commit_guard_checks_current_origin_ref_first(monkeypatch):
    pushed = "f" * 40
    checked = []

    def fake_run(command, **kwargs):
        if command[3:5] == ["ls-remote", "--heads"]:
            output = (
                f"{pushed}\trefs/heads/demo-stack-snowflake\n"
                f"{pushed}\trefs/heads/devin/feature\n"
            )
            return subprocess.CompletedProcess(command, 0, stdout=output, stderr="")
        if command[3:5] == ["branch", "--show-current"]:
            return subprocess.CompletedProcess(command, 0, stdout="devin/feature\n", stderr="")
        if "rev-parse" in command:
            return subprocess.CompletedProcess(command, 0, stdout=f"{pushed}\n", stderr="")
        if "merge-base" in command:
            checked.append(command[-1])
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        raise AssertionError(command)

    monkeypatch.setattr(git_utils.subprocess, "run", fake_run)
    ref = git_utils.require_pushed_commit("a" * 40, "/repo")
    assert ref == "refs/remotes/origin/devin/feature"
    assert checked == ["refs/remotes/origin/devin/feature"]
