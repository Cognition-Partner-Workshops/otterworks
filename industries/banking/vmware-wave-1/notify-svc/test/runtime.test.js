'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readConfig } = require('../src/config');
const { createApp } = require('../src/server');

test('configuration defaults preserve the VM connection', () => {
  assert.deepEqual(readConfig({}), { port: 3000, redisUrl: 'redis://127.0.0.1:6379', redisPassword: undefined });
});
test('configuration accepts environment and separate password', () => {
  assert.deepEqual(readConfig({ PORT: '8080', REDIS_URL: 'redis://redis.deps:6379/2', REDIS_PASSWORD: 'fixture' }),
    { port: 8080, redisUrl: 'redis://redis.deps:6379/2', redisPassword: 'fixture' });
});
test('configuration rejects empty and malformed inputs', () => {
  for (const PORT of ['', '0', '-1', '65536', '3.5', 'x']) assert.throws(() => readConfig({ PORT }), /PORT/);
  for (const REDIS_URL of ['', 'bad', 'http://redis', 'redis://:hidden@redis']) {
    assert.throws(() => readConfig({ REDIS_URL }), /REDIS_URL/);
  }
  assert.throws(() => readConfig({ REDIS_PASSWORD: '' }), /REDIS_PASSWORD/);
});

async function withApp(db, fn) {
  const server = createApp(db).listen(0, '127.0.0.1');
  await new Promise(resolve => server.once('listening', resolve));
  try { await fn('http://127.0.0.1:' + server.address().port); }
  finally { await new Promise(resolve => server.close(resolve)); }
}

test('health requires Redis PONG and handles errors, empty replies and timeout', async () => {
  for (const [ping, status] of [
    [cb => cb(null, 'PONG'), 200], [cb => cb(new Error('offline')), 503],
    [cb => cb(null, undefined), 503], [() => { throw new Error('offline'); }, 503],
    [() => {}, 503]
  ]) {
    await withApp({ ping }, async base => {
      const response = await fetch(base + '/health');
      assert.equal(response.status, status);
      assert.deepEqual(await response.json(), { healthy: status === 200 });
    });
  }
});

test('legacy enqueue and outbox response bytes remain unchanged', async () => {
  const rows = [];
  const db = {
    incr: (key, cb) => cb(null, 1), expire: () => {},
    lpush: (key, msg, cb) => { rows.unshift(msg); cb(null); },
    lrange: (key, start, end, cb) => cb(null, rows)
  };
  await withApp(db, async base => {
    assert.equal(await (await fetch(base + '/outbox/A0001')).text(), '[]');
    const response = await fetch(base + '/notify', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ account: 'A0001', kind: 'statement_ready' }) });
    assert.equal(response.status, 202);
    assert.equal(await response.text(), '{"queued":true,"text":"Your statement for ****0001 is ready to view."}');
    assert.equal(await (await fetch(base + '/outbox/A0001')).text(), '[' + rows[0] + ']');
    const invalid = await fetch(base + '/notify', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
    assert.equal(invalid.status, 400);
    assert.equal(await invalid.text(), '{"error":"account and kind are required"}');
  });
});
