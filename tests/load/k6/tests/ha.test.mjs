import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';

const root = new URL('../../../../', import.meta.url).pathname;
const read = (path) => readFileSync(join(root, path), 'utf8');

function run(args, env = {}) {
  const bin = mkdtempSync(join(tmpdir(), 'ha-runner-'));
  const log = join(bin, 'calls.jsonl');
  try {
    const stub = `#!/usr/bin/env node
const fs = require('node:fs');
const name = require('node:path').basename(process.argv[1]);
const args = process.argv.slice(2);
fs.appendFileSync(process.env.CALL_LOG, JSON.stringify([name, ...args]) + '\\n');
if (name === 'kubectl' && args[0] === 'apply' && process.env.FAIL_QUOTA) process.exit(1);
if (name === 'helm' && args[0] === 'status' && process.env.MISSING_SERVICE) process.exit(1);
`;
    for (const name of ['kubectl', 'helm']) writeFileSync(join(bin, name), stub, { mode: 0o700 });
    writeFileSync(log, '');
    const result = spawnSync('bash', [join(root, 'scripts/scale-for-load.sh'), ...args], {
      env: { ...process.env, ...env, PATH: `${bin}:${process.env.PATH}`, CALL_LOG: log },
      encoding: 'utf8',
    });
    const calls = readFileSync(log, 'utf8').trim().split('\n').filter(Boolean).map(JSON.parse);
    return { ...result, calls };
  } finally {
    rmSync(bin, { recursive: true, force: true });
  }
}

test('HA up provisions quota before upgrading and applies only matching CPU overlays', () => {
  const result = run(['example', 'up']);
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(result.calls[0], ['kubectl', 'apply', '-n', 'otterworks-example', '-f', join(root, 'infrastructure/k8s/tenant-ha-quota.yaml')]);
  const upgrades = result.calls.filter(([tool, verb]) => tool === 'helm' && verb === 'upgrade');
  assert.equal(upgrades.length, 5);
  for (const call of upgrades) {
    assert.ok(call.includes('--reuse-values'));
    assert.ok(call.includes(join(root, 'infrastructure/helm/profiles/high-availability.yaml')));
    const overlays = call.filter((arg) => /high-availability-.*\.yaml$/.test(arg));
    assert.deepEqual(overlays, ['document-service', 'auth-service'].includes(call[2])
      ? [join(root, `infrastructure/helm/profiles/high-availability-${call[2]}.yaml`)] : []);
  }
});

test('down leaves quota unchanged; empty input and quota errors cannot upgrade', () => {
  const down = run(['example', 'down', 'document-service']);
  assert.equal(down.status, 0, down.stderr);
  assert.ok(!down.calls.some(([tool, verb]) => tool === 'kubectl' && verb === 'apply'));
  const empty = run([]);
  assert.equal(empty.status, 1);
  assert.deepEqual(empty.calls, []);
  const failed = run(['example', 'up'], { FAIL_QUOTA: '1' });
  assert.equal(failed.status, 1);
  assert.equal(failed.calls.length, 1);
  const missing = run(['example', 'up', 'document-service'], { MISSING_SERVICE: '1' });
  assert.equal(missing.status, 0);
  assert.ok(!missing.calls.some(([tool, verb]) => tool === 'helm' && verb === 'upgrade'));
});

test('HA quota covers full tenant at core HPA max, rollout surge and the k6 Job', () => {
  const quota = read('infrastructure/k8s/tenant-ha-quota.yaml');
  const value = (key) => Number(quota.match(new RegExp(`    ${key.replaceAll('.', '\\.')}:[ "']*([0-9.]+)`))[1]);
  const max = Number(read('infrastructure/helm/profiles/high-availability.yaml').match(/maxReplicas: (\d+)/)[1]);
  const surge = Math.ceil(max * 0.25);
  assert.ok(value('limits.cpu') >= 6.25 + max * 4 + surge * 1.5 + 1);
  assert.ok(value('requests.cpu') >= 0.95 + max * 0.5 + surge * 0.1 + 0.1);
  assert.ok(value('requests.memory') * 1024 >= 2496 + max * 1024 + surge * 512 + 128);
  assert.ok(value('limits.memory') * 1024 >= 5120 + max * 2048 + surge * 1024 + 512);
  assert.ok(value('pods') >= 10 + max * 5 + surge + 1);
  for (const [svc, cpu] of [['document-service', '"1"'], ['auth-service', '1500m']]) {
    assert.equal(read(`infrastructure/helm/profiles/high-availability-${svc}.yaml`), `resources:\n  limits:\n    cpu: ${cpu}\n`);
  }
  assert.match(read('scripts/deploy-tenant.sh'), /limits.cpu: "12"/);
});
