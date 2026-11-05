'use strict';

const assert = require('assert');
const http = require('http');
const crypto = require('crypto');
const { createApp } = require('../src/server');

async function main() {
  const original = [process.env.NOTIFY_SEND_TOKEN, process.env.NOTIFY_OUTBOX_TOKEN];
  const send = crypto.randomBytes(32).toString('hex');
  const read = crypto.randomBytes(32).toString('hex');
  process.env.NOTIFY_SEND_TOKEN = send;
  process.env.NOTIFY_OUTBOX_TOKEN = read;
  const counters = {}, lists = {};
  let calls = 0, fail = false;
  const db = {
    incr(key, cb) { calls++; counters[key] = (counters[key] || 0) + 1; cb(fail ? new Error('store') : null, counters[key]); },
    expire(key, seconds) { assert.strictEqual(seconds, 3600); },
    lpush(key, value, cb) { calls++; (lists[key] || (lists[key] = [])).unshift(value); cb(fail ? new Error('store') : null); },
    lrange(key, start, end, cb) { calls++; cb(fail ? new Error('store') : null, (lists[key] || []).slice(start, end + 1)); }
  };
  const server = createApp(db).listen(0, '127.0.0.1');
  await new Promise(resolve => server.once('listening', resolve));
  function request(path, token, body) {
    return new Promise((resolve, reject) => {
      const headers = { 'Content-Type': 'application/json' };
      if (token) headers.Authorization = 'Bearer ' + token;
      const req = http.request({ hostname: '127.0.0.1', port: server.address().port, path, method: body ? 'POST' : 'GET', headers }, res => {
        let data = '';
        res.on('data', chunk => { data += chunk; });
        res.on('end', () => resolve({ status: res.statusCode, body: JSON.parse(data), headers: res.headers }));
      });
      req.on('error', reject);
      req.end(body ? JSON.stringify(body) : undefined);
    });
  }
  const message = { account: 'HG611000001', kind: 'statement_ready', fields: {} };
  try {
    for (const [path, body, wrong] of [['/notify', message, read], ['/outbox/HG611000001', undefined, send]]) {
      for (const token of [undefined, crypto.randomBytes(32).toString('hex'), wrong]) {
        const res = await request(path, token, body);
        assert.strictEqual(res.status, 401);
        assert.deepStrictEqual(res.body, { error: 'unauthorized' });
        assert.strictEqual(res.headers['www-authenticate'], 'Bearer');
      }
    }
    for (const value of [undefined, '']) {
      for (const [name, path, body] of [['NOTIFY_SEND_TOKEN', '/notify', message], ['NOTIFY_OUTBOX_TOKEN', '/outbox/HG611000001', undefined]]) {
        if (value === undefined) delete process.env[name]; else process.env[name] = value;
        const res = await request(path, send, body);
        assert.strictEqual(res.status, 503);
        assert.deepStrictEqual(res.body, { error: 'notify auth not configured' });
        process.env[name] = name === 'NOTIFY_SEND_TOKEN' ? send : read;
      }
    }
    for (const account of ['bad:key', 'hg611000001', {}, 'HG12345', 'HG611000001\n']) {
      assert.strictEqual((await request('/notify', send, Object.assign({}, message, { account }))).status, 400);
    }
    assert.strictEqual((await request('/outbox/bad:key', read)).status, 400);
    assert.strictEqual((await request('/outbox/HG611000001%0A', read)).status, 400);
    for (const merchant of ['https://example.invalid', 'www.example.invalid', 'line\nbreak', 'x'.repeat(65), {}]) {
      const res = await request('/notify', send, { account: message.account, kind: 'card_payment', fields: { amount: 12.4, merchant } });
      assert.strictEqual(res.status, 400);
      assert.deepStrictEqual(res.body, { error: 'invalid field: merchant' });
    }
    assert.strictEqual(calls, 0);
    const text = 'Your statement for ****0001 is ready to view.';
    const res = await request('/notify', send, message);
    assert.strictEqual(res.status, 202);
    assert.deepStrictEqual(res.body, { queued: true, text });
    const card = await request('/notify', send, { account: message.account, kind: 'card_payment', fields: { amount: '12.40', merchant: 'Corner Cafe' } });
    assert.strictEqual(card.status, 202);
    assert.strictEqual(card.body.text, 'Card payment of 12.40 on ****0001 at Corner Cafe.');
    const outbox = await request('/outbox/HG611000001', read);
    assert.strictEqual(outbox.status, 200);
    assert.deepStrictEqual(outbox.body.map(row => row.text), [card.body.text, text]);
    assert(outbox.body.every(row => row.account === message.account && !isNaN(Date.parse(row.at))));
    assert.deepStrictEqual((await request('/outbox/HG611000002', read)).body, []);
    for (let i = 2; i < 20; i++) assert.strictEqual((await request('/notify', send, message)).status, 202);
    assert.strictEqual((await request('/notify', send, message)).status, 429);
    fail = true;
    assert.deepStrictEqual((await request('/notify', send, message)).body, { error: 'store unavailable' });
    assert.deepStrictEqual((await request('/outbox/HG611000001', read)).body, { error: 'store unavailable' });
    console.log('server: auth, validation, parity, isolation, rate limit and store errors passed');
  } finally {
    await new Promise(resolve => server.close(resolve));
    ['NOTIFY_SEND_TOKEN', 'NOTIFY_OUTBOX_TOKEN'].forEach((name, i) => {
      if (original[i] === undefined) delete process.env[name]; else process.env[name] = original[i];
    });
  }
}
main().catch(err => { console.error(err); process.exitCode = 1; });
