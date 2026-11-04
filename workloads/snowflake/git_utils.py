"""Git guards shared by Snowflake deployment commands."""

from __future__ import annotations

import subprocess


def pushed_ref_for_commit(commit: str, repo: str = ".") -> str:
    """Return an origin branch containing commit, if the same ref is locally available."""
    remote_heads = subprocess.run(
        ["git", "-C", repo, "ls-remote", "--heads", "origin"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    for line in remote_heads.splitlines():
        remote_sha, remote_ref = line.split("\t", 1)
        branch = remote_ref.removeprefix("refs/heads/")
        local_ref = f"refs/remotes/origin/{branch}"
        local = subprocess.run(
            ["git", "-C", repo, "rev-parse", "--verify", "--quiet", local_ref],
            capture_output=True,
            text=True,
        )
        if local.returncode or local.stdout.strip() != remote_sha:
            continue
        ancestor = subprocess.run(
            ["git", "-C", repo, "merge-base", "--is-ancestor", commit, local_ref],
            capture_output=True,
        )
        if ancestor.returncode == 0:
            return local_ref
    raise ValueError(f"Commit {commit} is not an ancestor of any pushed origin branch")


def require_pushed_commit(commit: str, repo: str = ".") -> str:
    return pushed_ref_for_commit(commit, repo)
