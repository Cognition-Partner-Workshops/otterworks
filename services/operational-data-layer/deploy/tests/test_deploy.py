import json
import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[4]
SCRIPTS = ROOT / 'scripts/odl'


@pytest.fixture
def helm_stub(tmp_path, monkeypatch):
    log = tmp_path / 'helm.jsonl'
    helm = tmp_path / 'helm'
    helm.write_text(
        '#!/usr/bin/env python3\n'
        'import json, os, sys\n'
        'with open(os.environ["HELM_LOG"], "a") as out:\n'
        '    out.write(json.dumps(sys.argv[1:]) + "\\n")\n'
        'sys.exit(42 if os.environ.get("FAIL_HELM") else 0)\n'
    )
    helm.chmod(0o755)
    monkeypatch.setenv('PATH', f'{tmp_path}:{os.environ["PATH"]}')
    monkeypatch.setenv('HELM_LOG', str(log))
    return log


def invoke(*args, script='deploy-odl-ui.sh'):
    return subprocess.run(['bash', str(SCRIPTS / script), *args],
                          capture_output=True, text=True)


def test_ui_deployment_commands(helm_stub):
    result = invoke('odl')
    assert result.returncode == 0, result.stderr
    gateway, admin = [json.loads(line) for line in helm_stub.read_text().splitlines()]
    assert gateway[:2] == ['upgrade', 'api-gateway']
    assert '--reuse-values' in gateway
    assert admin[:3] == ['upgrade', '--install', 'admin-dashboard']
    for command, values in ((gateway, 't-odl-gateway.values.yaml'),
                            (admin, 't-odl-admin.values.yaml')):
        assert command[command.index('-n') + 1] == 'otterworks-odl'
        assert command[command.index('-f') + 1] == str(SCRIPTS / values)
        assert command[command.index('--post-renderer') + 1] == str(SCRIPTS / 'helm-labels.py')
        assert command[command.index('--labels') + 1] == 'run_token=odl-1795112287'
        assert '--wait' in command


@pytest.mark.parametrize('args', [(), ('main',), ('other',)])
@pytest.mark.parametrize('script', ['deploy-odl-ui.sh', 'deploy-odl-runtime.sh'])
def test_ui_rejects_missing_or_other_tenant(helm_stub, args, script):
    assert invoke(*args, script=script).returncode != 0
    assert not helm_stub.exists()


def test_runtime_deploy_does_not_reseed_sources(helm_stub):
    result = invoke('odl', script='deploy-odl-runtime.sh')
    assert result.returncode == 0, result.stderr
    runtime, gateway, admin = [json.loads(line) for line in helm_stub.read_text().splitlines()]
    assert runtime[:3] == ['upgrade', '--install', 'operational-data-layer']
    assert runtime[runtime.index('-n') + 1] == 'otterworks-odl'
    assert '--post-renderer' in runtime and '--wait' in runtime
    assert gateway[1] == 'api-gateway' and admin[2] == 'admin-dashboard'


def test_ui_stops_on_failed_gateway(helm_stub, monkeypatch):
    monkeypatch.setenv('FAIL_HELM', '1')
    assert invoke('odl').returncode == 42
    assert len(helm_stub.read_text().splitlines()) == 1


@pytest.mark.parametrize('tenant,mode,expected', [
    ('odl', 'after', True), ('odl', 'before', False),
    ('other', 'after', False), ('main', 'after', False),
])
def test_wrapper_ui_scope(tenant, mode, expected, tmp_path):
    script = (SCRIPTS / 'deploy-odl.sh').read_text()
    start = script.index('if [ "$MODE" = after ]')
    end = script.index('  helm upgrade --install operational-data-layer', start)
    guard = script[start:end] + 'fi\n'
    root = tmp_path / 'root'
    (root / 'services/operational-data-layer/deploy').mkdir(parents=True)
    (root / 'scripts/odl').mkdir(parents=True)
    helper = root / 'scripts/odl/deploy-odl-ui.sh'
    helper.write_text('#!/bin/sh\nprintf "UI:%s\\n" "$1"\n')
    helper.chmod(0o755)
    env = dict(os.environ, ROOT=str(root), ID=tenant, MODE=mode)
    result = subprocess.run(['bash', '-c', guard], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert ('UI:odl' in result.stdout) == expected


def test_pinned_ui_chart_rendering():
    for release, file in (('api-gateway', 't-odl-gateway.values.yaml'),
                          ('admin-dashboard', 't-odl-admin.values.yaml')):
        result = subprocess.run([
            'helm', 'template', release, str(ROOT / 'infrastructure/helm' / release),
            '-n', 'otterworks-odl', '-f', str(SCRIPTS / file),
            '--api-versions', 'monitoring.coreos.com/v1',
        ], check=True, capture_output=True, text=True)
        objects = [obj for obj in yaml.safe_load_all(result.stdout) if obj]
        service = next(obj for obj in objects if obj['kind'] == 'Service')
        assert service['spec']['type'] == 'ClusterIP'
        deployment = next(obj for obj in objects if obj['kind'] == 'Deployment')
        container = deployment['spec']['template']['spec']['containers'][0]
        values = yaml.safe_load((SCRIPTS / file).read_text())
        assert re.fullmatch(r'odl-[0-9a-f]+@sha256:[0-9a-f]{64}', values['image']['tag'])
        assert container['image'] == f"{values['image']['repository']}:{values['image']['tag']}"
        if release == 'api-gateway':
            env = {item['name']: item.get('value') for item in container['env']}
            assert env['ODL_SERVICE_URL'] == 'http://operational-data-layer:8098'
        else:
            ingress = next(obj for obj in objects if obj['kind'] == 'Ingress')
            rule = ingress['spec']['rules'][0]
            assert rule['host'] == 't-odl.demo.otterworks.app'
            path = rule['http']['paths'][0]
            assert path['path'] == '/admin(/|$)(.*)'
            assert path['backend']['service']['name'] == 'admin-dashboard'
            assert ingress['metadata']['annotations']['nginx.ingress.kubernetes.io/rewrite-target'] == '/$2'
            assert not any(obj['kind'] in ('ServiceMonitor', 'NetworkPolicy') for obj in objects)
