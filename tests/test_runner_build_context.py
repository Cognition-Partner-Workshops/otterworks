import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def tracked_tfvars():
    out = subprocess.run(['git', 'ls-files', '*.tfvars', '*.tfvars.json'], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout.split()
    return {p for p in out if not p.endswith('.example')}


def test_dockerignore_tfvars_exceptions_name_only_committed_files():
    exceptions = {line[1:] for line in (ROOT / '.dockerignore').read_text().splitlines()
                  if line.startswith('!') and 'tfvars' in line and not line.endswith('.example')}
    assert exceptions and all('*' not in e for e in exceptions)
    assert exceptions <= tracked_tfvars()


def test_runner_guard_exempts_only_committed_tfvars():
    dockerfile = (ROOT / 'demo-platform/runner/Dockerfile').read_text()
    exempt = [line.split("'")[1] for line in dockerfile.splitlines()
              if "! -path '/workspace/" in line and 'tfvars' in line]
    assert exempt and all('*' not in p for p in exempt)
    assert {p.removeprefix('/workspace/') for p in exempt} <= tracked_tfvars()
