'use strict';

const assert = require('assert');
const http = require('http');
const crypto = require('crypto');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { createApp } = require('../src/server');
const { loadAuthz, validateAuthz } = require('../src/authz');

async function run(authzFactory, check) {
  const send = crypto.randomBytes(32).toString('hex');
  const read = crypto.randomBytes(32).toString('hex');
  const hash = token => crypto.createHash('sha256').update(token).digest('hex');
  const config = { principals: [
    { name: 'producer', role: 'send', token_sha256: hash(send), accounts: ['HG611000001'] },
    { name: 'gateway', role: 'outbox', token_sha256: hash(read), accounts: ['HG611000001'] },
    { name: 'other-producer', role: 'send', token_sha256: hash(crypto.randomBytes(32)), accounts: ['HG621000002'] },
    { name: 'other-gateway', role: 'outbox', token_sha256: hash(crypto.randomBytes(32)), accounts: ['HG621000002'] }
  ] };
  const counters = {}, lists = {};
  let calls = 0, fail = false;
  const db = {
    incr(key, cb) { calls++; counters[key] = (counters[key] || 0) + 1; cb(fail ? new Error('store') : null, counters[key]); },
    expire(key, seconds) { assert.strictEqual(seconds, 3600); },
    lpush(key, value, cb) { calls++; (lists[key] || (lists[key] = [])).unshift(value); cb(fail ? new Error('store') : null); },
    lrange(key, start, end, cb) { calls++; cb(fail ? new Error('store') : null, (lists[key] || []).slice(start, end + 1)); }
  };
  const server = createApp(db, authzFactory(config)).listen(0, '127.0.0.1');
  await new Promise(resolve => server.once('listening', resolve));
  function request(path, token, body) {
    return new Promise((resolve, reject) => {
      const headers = { 'Content-Type': 'application/json', 'X-Principal': 'producer', 'X-Account': 'HG611000001' };
      if (token) headers.Authorization = 'Bearer ' + token;
      const req = http.request({ hostname: '127.0.0.1', port: server.address().port, path, method: body ? 'POST' : 'GET', headers }, res => {
        let data = '';
        res.on('data', chunk => { data += chunk; });
        res.on('end', () => resolve({ status: res.statusCode, body: JSON.parse(data), headers: res.headers }));
      });
      req.on('error', reject);
      req.end(typeof body === 'string' ? body : body ? JSON.stringify(body) : undefined);
    });
  }
  const message = { account: 'HG611000001', kind: 'statement_ready', fields: {} };
  try {
    if (check) {
      await check(request, send, read, message);
      assert.strictEqual(calls, 0);
      return;
    }
    for (const [path, body, wrong] of [['/notify', message, read], ['/outbox/HG611000001', undefined, send]]) {
      for (const token of [undefined, crypto.randomBytes(32).toString('hex'), wrong]) {
        const res = await request(path, token, body);
        assert.strictEqual(res.status, 401);
        assert.deepStrictEqual(res.body, { error: 'unauthorized' });
        assert.strictEqual(res.headers['www-authenticate'], 'Bearer');
      }
    }
    assert.strictEqual((await request('/notify', read, {})).status, 401);
    assert.strictEqual((await request('/notify', read, '{')).status, 401);
    assert.strictEqual((await request('/notify', send, {})).status, 400);
    for (const account of ['bad:key', 'hg611000001', {}, 'HG12345', 'HG611000001\n']) {
      assert.strictEqual((await request('/notify', send, Object.assign({}, message, { account }))).status, 400);
    }
    assert.strictEqual((await request('/outbox/bad:key', read)).status, 400);
    assert.strictEqual((await request('/outbox/HG611000001%0A', read)).status, 400);
    for (const [route, token, body] of [['/notify', send, Object.assign({}, message, { account: 'HG621000002', kind: 'nope' })], ['/outbox/HG621000002', read, undefined]]) {
      const res = await request(route, token, body);
      assert.strictEqual(res.status, 403);
      assert.deepStrictEqual(res.body, { error: 'forbidden' });
    }
    assert.strictEqual((await request('/notify', send, Object.assign({}, message, { kind: 'nope' }))).status, 400);
    assert.strictEqual((await request('/notify', send, Object.assign({}, message, { kind: 'card_payment' }))).status, 400);
    assert.strictEqual(calls, 0);
    assert.deepStrictEqual((await request('/outbox/HG611000001', read)).body, []);
    const text = 'Your statement for ****0001 is ready to view.';
    const res = await request('/notify', send, message);
    assert.strictEqual(res.status, 202);
    assert.deepStrictEqual(res.body, { queued: true, text });
    const merchant = 'https://example.invalid\nAct now';
    const card = await request('/notify', send, { account: message.account, kind: 'card_payment', fields: { amount: '12.40', merchant } });
    assert.strictEqual(card.status, 202);
    assert.deepStrictEqual(card.body, { queued: true, text: 'Card payment of 12.40 on ****0001 at ' + merchant + '.' });
    lists['notify:outbox:HG621000002'] = [JSON.stringify({ account: 'HG621000002', text: 'other account' })];
    const outbox = await request('/outbox/HG611000001', read);
    assert.strictEqual(outbox.status, 200);
    assert.deepStrictEqual(outbox.body.map(row => row.text), [card.body.text, text]);
    assert(outbox.body.every(row => row.account === message.account && !isNaN(Date.parse(row.at))));
    assert.strictEqual((await request('/outbox/HG621000002', read)).status, 403);
    for (let i = 2; i < 20; i++) assert.strictEqual((await request('/notify', send, message)).status, 202);
    assert.strictEqual((await request('/notify', send, message)).status, 429);
    fail = true;
    assert.deepStrictEqual((await request('/notify', send, message)).body, { error: 'store unavailable' });
    assert.deepStrictEqual((await request('/outbox/HG611000001', read)).body, { error: 'store unavailable' });
  } finally {
    await new Promise(resolve => server.close(resolve));
  }
}

async function unavailable(factory) {
  await run(factory, async (request, send, read, message) => {
    for (const [route, token, body] of [['/notify', send, message], ['/outbox/HG611000001', read, undefined]]) {
      const res = await request(route, token, body);
      assert.strictEqual(res.status, 503);
      assert.deepStrictEqual(res.body, { error: 'notify auth not configured' });
    }
  });
}

async function main() {
  const dir = fs.mkdtempSync(path.join(os.homedir(), '.notify-authz-test-'));
  const file = path.join(dir, 'authz.json');
  try {
    for (const value of [undefined, '', path.join(dir, 'missing'), dir]) {
      assert.strictEqual(loadAuthz(value), null);
      await unavailable(() => loadAuthz(value));
    }
    fs.writeFileSync(file, '{');
    await unavailable(() => loadAuthz(file));
    for (const value of [null, {}, { principals: {} }, { principals: [null] }, { principals: [] }]) {
      await unavailable(() => value);
    }
    await unavailable(config => {
      config.principals.push(config.principals[0]);
      assert.throws(() => validateAuthz(config), /invalid notify auth configuration/);
      return config;
    });
    for (const change of [{ name: '' }, { role: 'admin' }, { role: ['send', 'outbox'] }, { token_sha256: '' }, { token_sha256: 'x'.repeat(64) }, { accounts: ['*'] }, { accounts: ['HG611000001\n'] }, { accounts: [1] }, { accounts: 'all' }]) {
      await unavailable(config => {
        config.principals[0] = Object.assign({}, config.principals[0], change);
        assert.throws(() => validateAuthz(config), /invalid notify auth configuration/);
        fs.writeFileSync(file, JSON.stringify(config));
        assert.strictEqual(loadAuthz(file), null);
        return config;
      });
    }
    await run(config => {
      fs.writeFileSync(file, JSON.stringify(config));
      const loaded = loadAuthz(file);
      fs.writeFileSync(file, '{}');
      return loaded;
    });
    await run(config => {
      config.principals.forEach(p => { p.accounts = []; });
      return config;
    }, async (request, send, read, message) => {
      assert.strictEqual((await request('/notify', send, message)).status, 403);
      assert.strictEqual((await request('/outbox/HG611000001', read)).status, 403);
    });
    for (const role of ['send', 'outbox']) {
      await run(config => ({ principals: config.principals.filter(p => p.role !== role) }), async (request, send, read, message) => {
        assert.strictEqual((await request(role === 'send' ? '/notify' : '/outbox/HG611000001', role === 'send' ? send : read, role === 'send' ? message : undefined)).status, 503);
        assert.strictEqual((await request(role === 'send' ? '/outbox/HG611000001' : '/notify', role === 'send' ? send : read, role === 'send' ? undefined : message)).status, 401);
      });
    }
    console.log('server: principal grants, loader failures, payload parity, isolation, rate limit and store errors passed');
  } finally {
    if (fs.existsSync(file)) fs.unlinkSync(file);
    fs.rmdirSync(dir);
  }
}
main().catch(err => { console.error(err); process.exitCode = 1; });
