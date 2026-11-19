import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';

const source = readFileSync(new URL('../lib/config.js', import.meta.url), 'utf8');
let serial = 0;
async function config(env = {}) {
  globalThis.__ENV = { BASE_URL: 'https://api-t-example.demo.otterworks.app', ...env };
  return import(`data:text/javascript;base64,${Buffer.from(`${source}\n// ${serial++}`).toString('base64')}`);
}

test('all profiles build SLOs and valid executors', async () => {
  for (const PROFILE of ['smoke', 'load', 'baseline', 'peak', 'stress', 'spike', 'soak']) {
    const module = await config({ PROFILE });
    const options = module.buildOptions();
    assert.equal(options.scenarios[PROFILE].executor, PROFILE === 'smoke' ? 'constant-vus' : ['baseline', 'peak'].includes(PROFILE) ? 'ramping-arrival-rate' : 'ramping-vus');
    assert.equal(options.thresholds['http_req_failed{phase:journey}'][0].threshold, 'rate<0.01');
    for (const endpoint of module.endpoints) {
      assert.ok(options.thresholds[`http_req_duration{endpoint:${endpoint},phase:journey}`]);
      assert.deepEqual(options.thresholds[`endpoint_requests{endpoint:${endpoint},phase:journey}`], ['count>0']);
    }
    assert.equal(options.thresholds['http_req_failed{phase:journey}'][0].abortOnFail, PROFILE === 'smoke');
    for (const metric of ['checks', 'server_errors']) {
      assert.equal(options.thresholds[metric][0].abortOnFail, PROFILE === 'smoke');
    }
    for (const [metric, thresholds] of Object.entries(options.thresholds)) {
      if (metric.startsWith('http_req_duration')) {
        assert.ok(thresholds.every((threshold) => threshold.abortOnFail === false));
      }
    }
    assert.equal(options.thresholds['http_req_duration{endpoint:login,phase:journey}'][0].threshold, 'p(95)<1000');
    assert.equal(options.thresholds['http_req_duration{endpoint:documents_list,phase:journey}'][0].threshold, 'p(95)<800');
  }
});

test('peak is 3x baseline; scale factors and duration are honored', async () => {
  const baseline = (await config({ PROFILE: 'baseline' })).buildOptions().scenarios.baseline;
  const peak = (await config({ PROFILE: 'peak', RATE: '2', VUS: '2', DURATION: '1m' })).buildOptions().scenarios.peak;
  assert.equal(peak.stages[1].target, baseline.stages[1].target * 6);
  assert.equal(peak.maxVUs, 300);
  assert.equal(peak.stages.map((stage) => parseFloat(stage.duration)).reduce((a, b) => a + b), 60);
});

test('empty, malformed and credential-bearing targets fail closed', async () => {
  for (const BASE_URL of ['', 'api.example.com', 'https://user:pass@example.com', 'https://example.com/path', 'https://example.com?x=1']) {
    await assert.rejects(config({ BASE_URL }));
  }
});

test('main protection requires both smoke and explicit opt-in', async () => {
  for (const BASE_URL of ['https://api-t-main.otterworks.app', 'https://t-main.otterworks.app', 'http://api-gateway.otterworks-main.svc.cluster.local:8080']) {
    await assert.rejects(config({ BASE_URL }));
    await assert.rejects(config({ BASE_URL, PROFILE: 'peak', ALLOW_MAIN: '1' }));
    await assert.rejects(config({ BASE_URL, PROFILE: 'smoke', ALLOW_MAIN: '1' }));
    const readonly = await config({ BASE_URL, PROFILE: 'smoke', ALLOW_MAIN: '1', READ_ONLY: '1' });
    assert.equal(readonly.readOnly, true);
    assert.ok(!Object.keys(readonly.buildOptions().thresholds).some((key) => key.includes('endpoint:login')));
  }
});

test('invalid numeric controls, profile, run id and durations are rejected', async () => {
  for (const env of [{ RATE: '0' }, { VUS: '-1' }, { TARGET_VUS: '-1' }, { USERS: '1.5' }, { USERS: '201' }, { USERS: 'NaN' }, { PROFILE: 'unknown' }, { RUN_ID: '../unsafe' }]) {
    await assert.rejects(config(env));
  }
  const module = await config({ DURATION: 'forever' });
  assert.throws(() => module.buildOptions());
});

test('original load, stress, spike and soak VU shapes remain available', async () => {
  const load = (await config({ PROFILE: 'load' })).buildOptions().scenarios.load;
  assert.deepEqual(load.stages, [{ duration: '120s', target: 50 }, { duration: '600s', target: 50 }, { duration: '120s', target: 0 }]);
  const stress = (await config({ PROFILE: 'stress', TARGET_VUS: '10' })).buildOptions().scenarios.stress;
  assert.deepEqual(stress.stages.map((stage) => stage.target), [10, 20, 30, 40, 0]);
  const soak = (await config({ PROFILE: 'soak' })).buildOptions().scenarios.soak;
  assert.equal(soak.stages.reduce((sum, stage) => sum + parseFloat(stage.duration), 0), 4200);
});

test('cluster runner rejects missing targets and protected namespaces before kubectl', () => {
  const bin = mkdtempSync(join(tmpdir(), 'k6-runner-'));
  try {
    writeFileSync(join(bin, 'kubectl'), '#!/bin/sh\necho "kubectl blocked by runner test" >&2\nexit 99\n', { mode: 0o700 });
    const run = (env) => spawnSync('bash', [new URL('../k8s/run.sh', import.meta.url).pathname], {
      env: { ...process.env, PATH: `${bin}:${process.env.PATH}`, BASE_URL: 'https://api-t-example.demo.otterworks.app', ...env },
      encoding: 'utf8',
    });
    assert.equal(run({ BASE_URL: '' }).status, 1);
    for (const NAMESPACE of ['otterworks-main', 'otterworks-platform', 'otterworks-system', 'default', 'kube-system', 'workbench']) {
      const result = run({ NAMESPACE });
      assert.equal(result.status, 2, result.stderr);
      assert.ok(!result.stderr.includes('kubectl blocked'));
    }
    for (const BASE_URL of ['https://api-t-main.demo.otterworks.app', 'https://example.com', 'https://api-t-example.demo.otterworks.app/path']) {
      const result = run({ NAMESPACE: 'otterworks-example', BASE_URL });
      assert.equal(result.status, 2, result.stderr);
      assert.ok(!result.stderr.includes('kubectl blocked'));
    }
  } finally {
    rmSync(bin, { recursive: true, force: true });
  }
});
