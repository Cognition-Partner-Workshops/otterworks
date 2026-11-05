"""Scan public repositories on main: --repos JSON_ARRAY --out report.sarif --work DIR."""

import argparse
import hashlib
import json
import os
import re
import secrets
import subprocess
import time
from pathlib import Path

import requests
from sonar_sarif import build_run, collect, document


def run(*args, **kwargs):
    return subprocess.check_output(args, text=True, **kwargs).strip()


def project_key(repo):
    readable = re.sub(r"[^A-Za-z0-9_.-]+", "_", repo).strip("_")
    digest = hashlib.sha256(repo.encode()).hexdigest()[:10]
    return f"{readable}_{digest}"


def validate_repositories(repos):
    if len(repos) != len(set(repos)):
        raise ValueError("repos must not contain duplicate entries")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repos", required=True, help="JSON array of owner/repository names")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    args = parser.parse_args()
    repos = json.loads(args.repos)
    if not isinstance(repos, list) or not repos or any(not isinstance(r, str) or not re.fullmatch(r"[\w.-]+/[\w.-]+", r) for r in repos):
        parser.error("repos must be a nonempty JSON array of owner/repository names")
    try:
        validate_repositories(repos)
    except ValueError as error:
        parser.error(str(error))
    host = os.environ.get("SONAR_HOST_URL", "http://localhost:9000")
    for _ in range(120):
        try:
            if requests.get(f"{host}/api/system/status", timeout=5).json().get("status") == "UP":
                break
        except requests.RequestException:
            pass
        time.sleep(5)
    else:
        raise RuntimeError("SonarQube did not become ready")
    password = "Aa9!" + secrets.token_urlsafe(32)
    default = "admin"  # gitleaks:allow
    response = requests.post(f"{host}/api/users/change_password", auth=(default, default),
                             data={"login": default, "previousPassword": default, "password": password}, timeout=30)
    response.raise_for_status()
    response = requests.post(f"{host}/api/user_tokens/generate", auth=(default, password),
                             data={"name": "local-scan"}, timeout=30)
    response.raise_for_status()
    token = response.json()["token"]
    args.work.mkdir(parents=True, exist_ok=True)
    runs = []
    for repo in repos:
        key = project_key(repo)
        path = args.work.resolve() / key
        run("git", "clone", "--depth", "1", "--branch", "main", f"https://github.com/{repo}.git", str(path))
        sha = run("git", "rev-parse", "HEAD", cwd=path)
        print(f"{repo}@{sha}", flush=True)
        subprocess.run(["docker", "run", "--rm", "--network", "host", "-e", "SONAR_TOKEN", "-e", "SONAR_HOST_URL",
            "-v", f"{path}:/usr/src:ro", "sonarsource/sonar-scanner-cli:12.3.1.4302_8.3.1",
            f"-Dsonar.projectKey={key}", "-Dsonar.sources=.", "-Dsonar.java.binaries=/tmp",
            "-Dsonar.working.directory=/tmp/scannerwork", "-Dsonar.scm.disabled=true",
            "-Dsonar.exclusions=**/node_modules/**,**/vendor/**,**/build/**,**/target/**,**/*.min.js,**/generated/**",
            "-Dsonar.cpd.exclusions=**/*", "-Dsonar.qualitygate.wait=false"], check=True,
            env={**os.environ, "SONAR_TOKEN": token, "SONAR_HOST_URL": host})
        for _ in range(240):
            response = requests.get(f"{host}/api/ce/component", auth=(token, ""), params={"component": key}, timeout=30)
            response.raise_for_status()
            task = response.json()
            if not task.get("queue") and task.get("current", {}).get("status") == "SUCCESS":
                break
            if task.get("current", {}).get("status") in ("FAILED", "CANCELED") and not task.get("queue"):
                raise RuntimeError(f"Analysis failed: {key}")
            time.sleep(5)
        else:
            raise RuntimeError(f"Analysis timed out: {key}")
        rows, rules = collect(host, token, key)
        runs.append(build_run(repo, sha, rows, rules))
        print(f"{repo}: {len(runs[-1]['results'])}", flush=True)
    args.out.write_text(json.dumps(document(runs), indent=2))


if __name__ == "__main__":
    main()
