"""Offline regression tests for scripts/demo-reaper.sh and scripts/demo-destroy.sh.

The real scripts and scripts/lib run against stub aws/az/kubectl/helm/terraform
binaries in a throwaway tree; nothing reaches a cloud API.

    python3 -m pytest scripts/tests -q
"""
import json
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
TOKEN = "zz9-after"
NS = f"otterworks-{TOKEN}"
PAST = "2020-01-01T00:00:00Z"
FUTURE = "2099-01-01T00:00:00Z"

AWS_STUB = r"""#!/usr/bin/env bash
echo "aws $*" >> "$STUB_LOG"
case "$1 $2" in
  "sts get-caller-identity") exit "${STUB_AWS_STS_RC:-0}" ;;
  "resourcegroupstaggingapi get-resources")
    [ "${STUB_AWS_GR_RC:-0}" = "0" ] || { echo "ThrottlingException" >&2; exit "${STUB_AWS_GR_RC}"; }
    if [[ " $* " == *" Key=demo,"* ]]; then cat "$STUB_AWS_RESOURCES"; else echo ""; fi ;;
  "ec2 describe-volumes"|"ecr describe-repositories"|"s3api head-bucket") exit "${STUB_AWS_EXISTS_RC:-0}" ;;
  "s3api list-buckets") echo "" ;;
  *) exit 0 ;;
esac
"""

KUBECTL_STUB = r"""#!/usr/bin/env bash
echo "kubectl $*" >> "$STUB_LOG"
if [ "$1 $2" = "get ns" ]; then
  if [[ " $* " == *" -l "* ]]; then cat "$STUB_K8S_NS"; exit 0; fi
  [ $# -eq 2 ] && exit "${STUB_K8S_RC:-0}"
  exit 1
fi
[ "$1 $2" = "get pv" ] && exit 0
exit 0
"""

# Azure control plane model: the resource group (and its Key Vault) exists until
# `group delete` is followed by deletion completing (`group wait --deleted`);
# only then is the vault listed as soft-deleted and purgeable.
AZ_STUB = r"""#!/usr/bin/env bash
echo "az $*" >> "$STUB_LOG"
S="$STUB_AZ_STATE"; touch "$S"
case "$1 $2" in
  "account show") [[ " $* " == *" --query id "* ]] && echo "$AZURE_SUBSCRIPTION_ID"; exit 0 ;;
  "group exists") if grep -q deleted "$S"; then echo false; else echo true; fi ;;
  "group delete") echo deleting >> "$S" ;;
  "group wait") grep -q deleting "$S" && echo deleted >> "$S"; exit 0 ;;
  "storage blob") echo true ;;
  "keyvault list-deleted") grep -q deleted "$S" && echo "kvowzz9after00"; exit 0 ;;
  "keyvault purge") echo purged >> "$S" ;;
  "resource list"|"group list") echo "[]" ;;
esac
exit 0
"""

TERRAFORM_STUB = r"""#!/usr/bin/env bash
echo "terraform $*" >> "$STUB_LOG"
[[ " $* " == *" destroy "* ]] && exit "${STUB_TF_DESTROY_RC:-0}"
exit 0
"""

LOGGING_STUB = """#!/usr/bin/env bash
echo "$(basename "$0") $*" >> "$STUB_LOG"
exit 0
"""


def _write_exec(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


@pytest.fixture
def sandbox(tmp_path):
    root = tmp_path / "repo"
    shutil.copytree(REPO / "scripts" / "lib", root / "scripts" / "lib")
    for name in ("demo-reaper.sh", "demo-destroy.sh"):
        shutil.copy2(REPO / "scripts" / name, root / "scripts" / name)
    (root / "infrastructure" / "terraform" / "azure").mkdir(parents=True)
    bin_dir = tmp_path / "bin"
    _write_exec(bin_dir / "aws", AWS_STUB)
    _write_exec(bin_dir / "kubectl", KUBECTL_STUB)
    _write_exec(bin_dir / "az", AZ_STUB)
    _write_exec(bin_dir / "terraform", TERRAFORM_STUB)
    _write_exec(bin_dir / "helm", LOGGING_STUB)
    for name in ("demo-destroy.sh", "teardown-tenant.sh"):
        target = root / "scripts" / name
        if name == "demo-destroy.sh":
            target = root / "scripts" / "stub-demo-destroy.sh"
        _write_exec(target, LOGGING_STUB)
    log = tmp_path / "calls.log"
    log.touch()
    env = {
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "HOME": str(tmp_path),
        "STUB_LOG": str(log),
        "STUB_AWS_RESOURCES": str(tmp_path / "aws.json"),
        "STUB_K8S_NS": str(tmp_path / "ns.json"),
        "STUB_AZ_STATE": str(tmp_path / "az.state"),
        "DEMO_DIR": str(tmp_path / "demo"),
        "AWS_REGION": "us-east-1",
        "AWS_ACCOUNT_ID": "000000000000",
        "KUBERNETES_SERVICE_HOST": "stub",
    }
    return root, env, log


def _aws(entries):
    return {"ResourceTagMappingList": [
        {"ResourceARN": arn, "Tags": [{"Key": "demo", "Value": "legacy-data-migration"},
                                      {"Key": "namespace", "Value": TOKEN},
                                      {"Key": "expires", "Value": exp}]}
        for arn, exp in entries]}


def _ns(expires):
    return {"items": [{"metadata": {
        "name": NS,
        "labels": {"demo/namespace": TOKEN, "demo/name": "legacy-data-migration"},
        "annotations": {"demo/expires": expires}}}]}


def run_reaper(sandbox, aws_entries, ns_expires, *, extra_env=None, args=("--apply",)):
    root, env, log = sandbox
    # demo-reaper.sh calls ${SCRIPT_DIR}/demo-destroy.sh; point that at the logging stub.
    reaper = root / "scripts" / "demo-reaper.sh"
    shutil.copy2(root / "scripts" / "stub-demo-destroy.sh", root / "scripts" / "demo-destroy.sh")
    Path(env["STUB_AWS_RESOURCES"]).write_text(json.dumps(_aws(aws_entries)))
    Path(env["STUB_K8S_NS"]).write_text(json.dumps(_ns(ns_expires)))
    proc = subprocess.run(["bash", str(reaper), *args], env={**env, **(extra_env or {})},
                          capture_output=True, text=True, timeout=60)
    destroys = [ln for ln in log.read_text().splitlines() if ln.startswith("demo-destroy.sh")]
    return proc, destroys


VOL = "arn:aws:ec2:us-east-1:000000000000:volume/vol-0123456789abcdef0"


def test_reaper_destroys_fully_expired_token(sandbox):
    proc, destroys = run_reaper(sandbox, [(VOL, PAST)], PAST)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert destroys == [f"demo-destroy.sh {TOKEN}"]


def test_reaper_skips_token_with_live_aws_tag(sandbox):
    proc, destroys = run_reaper(sandbox, [(VOL, FUTURE)], PAST)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert destroys == []


def test_reaper_fails_closed_when_aws_discovery_errors(sandbox):
    # Redeploy with a longer TTL in flight: AWS tags already say FUTURE, the namespace
    # annotation is still the old PAST value. A throttled tagging query must not turn
    # the stale annotation into a destroy.
    proc, destroys = run_reaper(sandbox, [(VOL, FUTURE)], PAST, extra_env={"STUB_AWS_GR_RC": "255"})
    assert destroys == [], proc.stdout + proc.stderr
    assert proc.returncode != 0


def test_reaper_fails_closed_when_aws_credentials_fail(sandbox):
    proc, destroys = run_reaper(sandbox, [(VOL, FUTURE)], PAST, extra_env={"STUB_AWS_STS_RC": "255"})
    assert destroys == [], proc.stdout + proc.stderr
    assert proc.returncode != 0


def test_reaper_fails_closed_when_kubernetes_discovery_errors(sandbox):
    proc, destroys = run_reaper(sandbox, [(VOL, PAST)], FUTURE, extra_env={"STUB_K8S_RC": "1"})
    assert destroys == [], proc.stdout + proc.stderr
    assert proc.returncode != 0


def test_reaper_unverifiable_live_arn_still_protects_token(sandbox):
    # describe-volumes failing (throttle/AccessDenied) must not silently drop the only
    # live evidence for the token.
    proc, destroys = run_reaper(sandbox, [(VOL, FUTURE)], PAST, extra_env={"STUB_AWS_EXISTS_RC": "255"})
    assert destroys == [], proc.stdout + proc.stderr


def test_reaper_ignores_stale_expired_arn(sandbox):
    proc, destroys = run_reaper(sandbox, [(VOL, PAST)], PAST, extra_env={"STUB_AWS_EXISTS_RC": "255"})
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert destroys == [f"demo-destroy.sh {TOKEN}"]


def test_reaper_skips_token_with_unreadable_expires(sandbox):
    proc, destroys = run_reaper(sandbox, [(VOL, "not-a-date")], PAST)
    assert destroys == [], proc.stdout + proc.stderr


def test_reaper_dry_run_never_destroys(sandbox):
    proc, destroys = run_reaper(sandbox, [(VOL, PAST)], PAST, args=("--dry-run",))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert destroys == []
    assert "[dry-run] would run: scripts/demo-destroy.sh " + TOKEN in proc.stdout


AZURE_ENV = {
    "AZURE_CLIENT_ID": "stub", "AZURE_CLIENT_SECRET": "stub", "AZURE_TENANT_ID": "stub",
    "AZURE_SUBSCRIPTION_ID": "00000000-0000-0000-0000-000000000000",
    "TFSTATE_AZ_ACCOUNT": "stub", "TFSTATE_AZ_RESOURCE_GROUP": "stub", "TFSTATE_AZ_CONTAINER": "tfstate",
}


def run_destroy(sandbox, *, extra_env=None):
    root, env, log = sandbox
    Path(env["STUB_AWS_RESOURCES"]).write_text(json.dumps(_aws([])))
    Path(env["STUB_K8S_NS"]).write_text(json.dumps({"items": []}))
    proc = subprocess.run(["bash", str(root / "scripts" / "demo-destroy.sh"), TOKEN, "--skip-verify"],
                          env={**env, **AZURE_ENV, "STUB_K8S_RC": "1", **(extra_env or {})},
                          capture_output=True, text=True, timeout=60)
    return proc, log.read_text().splitlines(), Path(env["STUB_AZ_STATE"]).read_text()


def test_destroy_purges_key_vault_after_resource_group_fallback(sandbox):
    # Terraform destroy fails (e.g. missing tfvars on the reaper runner) -> the
    # resource-group delete fallback runs; the vault only becomes purgeable once that
    # asynchronous delete completes, so the purge must happen after it.
    proc, calls, az_state = run_destroy(sandbox, extra_env={"STUB_TF_DESTROY_RC": "1"})
    assert any(c.startswith("az group delete") for c in calls), proc.stdout
    assert "purged" in az_state.split(), proc.stdout + proc.stderr
    assert any(c.startswith("az keyvault purge -n kvowzz9after00") for c in calls)


def _required_azure_vars():
    text = (REPO / "infrastructure" / "terraform" / "azure" / "variables.tf").read_text()
    out = []
    for name, body in re.findall(r'variable "([a-z0-9_]+)" \{(.*?)\n\}', text, re.S):
        if not re.search(r"^\s*default\s*=", body, re.M):
            out.append(name)
    return out


def test_destroy_without_tfvars_supplies_every_required_azure_variable(sandbox):
    proc, calls, _ = run_destroy(sandbox)
    destroy = [c for c in calls if c.startswith("terraform ") and " destroy " in f" {c} "]
    assert destroy, proc.stdout + proc.stderr
    supplied = set(re.findall(r"-var (\w+)=", destroy[0]))
    env_supplied = {"registry_password", "registry_username"}  # TF_VAR_* exported by the script
    missing = [v for v in _required_azure_vars() if v not in supplied | env_supplied]
    assert not missing, f"terraform destroy would fail with 'No value for required variable': {missing}"
