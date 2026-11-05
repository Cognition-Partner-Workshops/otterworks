"""Git guards shared by Snowflake deployment commands."""

from __future__ import annotations

import os
import subprocess


def pushed_ref_for_commit(commit: str, repo: str = ".") -> str:
    """Return an origin branch containing commit, if the same ref is locally available."""
    remote_heads = subprocess.run(
        ["git", "-C", repo, "ls-remote", "--heads", "origin"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    remote_refs = [line.split("\t", 1) for line in remote_heads.splitlines()]
    current_branch = subprocess.run(
        ["git", "-C", repo, "branch", "--show-current"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    preferred_branches = []
    for branch in (current_branch, os.environ.get("GITHUB_REF_NAME", "")):
        if branch:
            ref = f"refs/heads/{branch.removeprefix('refs/heads/')}"
            if ref not in preferred_branches:
                preferred_branches.append(ref)
    ordered_refs = [
        pair for preferred in preferred_branches for pair in remote_refs if pair[1] == preferred
    ]
    preferred_set = set(preferred_branches)
    ordered_refs.extend(pair for pair in remote_refs if pair[1] not in preferred_set)
    for remote_sha, remote_ref in ordered_refs:
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
