import base64
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[3]


@pytest.mark.skipif(shutil.which("helm") is None, reason="helm not installed")
def test_reindex_helm_consumers_receive_the_same_scoped_service_credential():
    for service in ("file-service", "search-service"):
        rendered = subprocess.check_output(
            [
                "helm",
                "template",
                service,
                str(REPO / "infrastructure/helm" / service),
                "--set-string",
                "secrets.FILE_REINDEX_TOKEN=test-install-credential",
                "--set-string",
                "image.tag=regression-test",
                "--set-string",
                "config.FILE_REINDEX_OWNER_PREFIX=12345678-",
            ],
            text=True,
        )
        objects = [item for item in yaml.safe_load_all(rendered) if item]
        secret = next(item for item in objects if item["kind"] == "Secret")
        deployment = next(item for item in objects if item["kind"] == "Deployment")
        assert secret["stringData"]["FILE_REINDEX_TOKEN"] == "test-install-credential"
        if service == "file-service":
            config = next(item for item in objects if item["kind"] == "ConfigMap")
            assert config["data"]["FILE_REINDEX_OWNER_PREFIX"] == "12345678-"
            assert any(
                entry.get("configMapRef", {}).get("name") == config["metadata"]["name"]
                for entry in deployment["spec"]["template"]["spec"]["containers"][0][
                    "envFrom"
                ]
            )
        container = deployment["spec"]["template"]["spec"]["containers"][0]
        assert any(
            entry.get("secretRef", {}).get("name") == secret["metadata"]["name"]
            for entry in container["envFrom"]
        )


@pytest.mark.parametrize("missing", [False, True])
def test_generated_admin_secret_is_passed_to_grafana_without_other_keys(
    tmp_path, missing
):
    kubectl = tmp_path / "kubectl"
    kubectl.write_text("""#!/usr/bin/env python3
import os,sys,json
from pathlib import Path
root=Path(os.environ["TEST_ROOT"])
args=sys.argv[1:]
with (root/"calls").open("a") as out: out.write(json.dumps(args)+"\\n")
if "namespace" in args:
 print("namespace/monitoring")
elif "deployments" in args:
 print(json.dumps({"items":[{"metadata":{"name":"shared-grafana"}}]}))
elif "get" in args and "secret" in args:
 print((root/"source").read_text())
elif "apply" in args:
 (root/"copied").write_text(sys.stdin.read())
""")
    kubectl.chmod(0o755)
    encoded = base64.b64encode(b"generated-at-install").decode()
    (tmp_path / "source").write_text(
        json.dumps(
            {
                "data": {
                    "ALERT_WEBHOOK_SECRET": "" if missing else encoded,
                    "JWT_SECRET": "must-not-copy",
                    "DATABASE_PASSWORD": "must-not-copy",
                }
            }
        )
    )
    env = {
        **os.environ,
        "PATH": f"{tmp_path}:/usr/bin:/bin",
        "TEST_ROOT": str(tmp_path),
        "ADMIN_NAMESPACE": "otterworks",
        "GRAFANA_NAMESPACE": "monitoring",
    }
    result = subprocess.run(
        ["bash", str(REPO / "scripts/sync-grafana-webhook-secret.sh")],
        env=env,
        capture_output=True,
        text=True,
    )
    calls = [json.loads(line) for line in (tmp_path / "calls").read_text().splitlines()]
    if missing:
        assert result.returncode != 0
        assert not any("set" in call or "rollout" in call for call in calls)
        return
    assert result.returncode == 0, result.stderr
    copied = json.loads((tmp_path / "copied").read_text())
    assert copied["metadata"] == {
        "name": "admin-alert-webhook",
        "namespace": "monitoring",
    }
    assert copied["data"] == {"ALERT_WEBHOOK_SECRET": encoded}
    assert any("--from=secret/admin-alert-webhook" in call for call in calls)
    assert any(
        "restart" in call and "deployment/shared-grafana" in call for call in calls
    )
    assert encoded not in result.stdout + result.stderr
    assert "generated-at-install" not in (tmp_path / "calls").read_text()


def test_compose_admin_and_grafana_share_the_same_webhook_environment():
    admin = yaml.safe_load((REPO / "docker-compose.yml").read_text())
    infra = yaml.safe_load((REPO / "docker-compose.infra.yml").read_text())
    assert (
        admin["services"]["admin-service"]["environment"]["ALERT_WEBHOOK_SECRET"]
        == infra["services"]["grafana"]["environment"]["ALERT_WEBHOOK_SECRET"]
    )
    contact = yaml.safe_load(
        (
            REPO / "observability/grafana/provisioning/alerting/contact-points.yml"
        ).read_text()
    )
    assert (
        contact["contactPoints"][0]["receivers"][0]["settings"][
            "authorization_credentials"
        ]
        == "$ALERT_WEBHOOK_SECRET"
    )
    assert (
        "sync-grafana-webhook-secret.sh" in (REPO / "scripts/deploy-dev.sh").read_text()
    )


@pytest.mark.parametrize(
    "scenario,expected",
    [
        ("absent", 0),
        ("absent_explicit", 0),
        ("empty", 0),
        ("forbidden", 7),
        ("unavailable", 7),
    ],
)
def test_optional_grafana_installation_does_not_hide_api_failures(
    tmp_path, scenario, expected
):
    kubectl = tmp_path / "kubectl"
    kubectl.write_text("""#!/usr/bin/env python3
import os,sys,json
from pathlib import Path
args=sys.argv[1:]
with (Path(os.environ["TEST_ROOT"])/"calls").open("a") as out:
 out.write(json.dumps(args)+"\\n")
scenario=os.environ["SCENARIO"]
if "namespace" in args:
 assert "--ignore-not-found" in args
 if scenario in ("forbidden", "unavailable"):
  print(scenario,file=sys.stderr)
  sys.exit(7)
 if not scenario.startswith("absent"): print("namespace/monitoring")
elif "deployments" in args:
 if scenario.startswith("absent"):
  print('namespaces "monitoring" not found',file=sys.stderr)
  sys.exit(1)
 print(json.dumps({"items":[]}))
else:
 sys.exit(99)
""")
    kubectl.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{tmp_path}:/usr/bin:/bin",
        "TEST_ROOT": str(tmp_path),
        "SCENARIO": scenario,
        "GRAFANA_NAMESPACE": "monitoring",
        "GRAFANA_DEPLOYMENT": "",
    }
    if scenario == "absent_explicit":
        env["GRAFANA_DEPLOYMENT"] = "explicit-grafana"
    result = subprocess.run(
        ["bash", str(REPO / "scripts/sync-grafana-webhook-secret.sh")],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == expected, result.stderr
    calls = [json.loads(line) for line in (tmp_path / "calls").read_text().splitlines()]
    assert all(
        "secret" not in call and "set" not in call and "rollout" not in call
        for call in calls
    )
    if scenario != "empty":
        assert not any("deployments" in call for call in calls)
