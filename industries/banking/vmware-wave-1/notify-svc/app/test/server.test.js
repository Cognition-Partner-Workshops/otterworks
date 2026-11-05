'use strict';

const assert = require('node:assert/strict');
const { test } = require('node:test');
const { createApp } = require('../src/server');
const { render, maskAccount } = require('../src/templates');

class FakeRedis {
  constructor() {
    this.counters = new Map();
    this.outboxes = new Map();
    this.expirations = [];
  }
  async ping() { return 'PONG'; }
  async incr(key) {
    const value = (this.counters.get(key) || 0) + 1;
    this.counters.set(key, value);
    return value;
  }
  async expire(key, seconds) { this.expirations.push([key, seconds]); }
  async lPush(key, row) {
    this.outboxes.set(key, [row, ...(this.outboxes.get(key) || [])]);
  }
  async lRange(key, start, end) { return (this.outboxes.get(key) || []).slice(start, end + 1); }
}

async function fixture(t, db = new FakeRedis()) {
  const server = createApp(db).listen(0, '127.0.0.1');
  await new Promise((resolve) => server.once('listening', resolve));
  t.after(() => new Promise((resolve) => {
    server.closeAllConnections();
    server.close(resolve);
  }));
  const base = 'http://127.0.0.1:' + server.address().port;
  return { db, get: (path) => fetch(base + path),
    post: (body, type = 'application/json', path = '/notify') => fetch(base + path, {
      method: 'POST', headers: { 'Content-Type': type },
      body: typeof body === 'string' ? body : JSON.stringify(body)
    }) };
}

const html = (text) => '<!DOCTYPE html>\n<html lang="en">\n<head>\n' +
  '<meta charset="utf-8">\n<title>Error</title>\n</head>\n<body>\n<pre>' +
  text + '</pre>\n</body>\n</html>\n';

test('legacy template assertions and short mask', () => {
  assert.equal(maskAccount('HG611000001'), '****0001');
  assert.equal(maskAccount('1234'), '1234');
  assert.equal(render('card_payment', { amount: '12.40', account: '****0001', merchant: 'Corner Cafe' }),
    'Card payment of 12.40 on ****0001 at Corner Cafe.');
  assert.throws(() => render('card_payment', { account: 'x' }), /missing field: amount/);
  assert.throws(() => render('nope', {}), /unknown notification kind/);
});

test('health success has no store mutations; rejected and hung PING fail', async (t) => {
  const f = await fixture(t);
  let response = await f.get('/health');
  assert.equal(response.status, 200);
  assert.equal(await response.text(), '{"status":"ok"}');
  assert.equal(f.db.counters.size, 0);
  f.db.ping = async () => { throw new Error('offline'); };
  response = await f.get('/health');
  assert.equal(response.status, 503);
  f.db.ping = () => new Promise(() => {});
  const start = Date.now();
  response = await f.get('/health');
  assert.equal(response.status, 503);
  assert.ok(Date.now() - start < 1800);
});

test('POST templates, raw JSON output, reverse outbox order, and empty outbox', async (t) => {
  const f = await fixture(t);
  assert.equal(await (await f.get('/outbox/unknown')).text(), '[]');
  const inputs = [
    ['statement_ready', {}, 'Your statement for 1234 is ready to view.'],
    ['card_payment', { amount: 12.4, merchant: 'Café Zürich' }, 'Card payment of 12.4 on 1234 at Café Zürich.'],
    ['low_balance', { threshold: '100.00' }, 'The balance on 1234 is below 100.00.']
  ];
  for (const [kind, fields, text] of inputs) {
    const response = await f.post({ account: '1234', kind, fields });
    assert.equal(response.status, 202);
    assert.equal(response.headers.get('content-type'), 'application/json; charset=utf-8');
    assert.equal(await response.text(), JSON.stringify({ queued: true, text }));
  }
  assert.deepEqual(f.db.expirations, [['notify:rate:1234', 3600]]);
  const rows = await (await f.get('/outbox/1234')).json();
  assert.deepEqual(rows.map((row) => row.text), inputs.map((row) => row[2]).reverse());
  assert.ok(rows.every((row) => row.account === '1234' && /Z$/.test(row.at)));
});

test('validation and production HTML errors match VM bytes', async (t) => {
  const f = await fixture(t);
  for (const [body, error] of [
    [{}, 'account and kind are required'],
    [{ kind: 'statement_ready' }, 'account and kind are required'],
    [{ account: 'x' }, 'account and kind are required'],
    [{ account: 'x', kind: 'nope' }, 'unknown notification kind: nope'],
    [{ account: 'x', kind: 'card_payment' }, 'missing field: amount'],
    [{ account: 'x', kind: 'card_payment', fields: { amount: 1 } }, 'missing field: merchant'],
    [{ account: 'x', kind: 'low_balance' }, 'missing field: threshold']
  ]) {
    const response = await f.post(body);
    assert.equal(response.status, 400);
    assert.equal(await response.text(), JSON.stringify({ error }));
  }
  let response = await f.post('not json', 'text/plain');
  assert.equal(response.status, 400);
  assert.equal(await response.text(), '{"error":"account and kind are required"}');
  response = await f.post('{"account":');
  assert.equal(response.status, 400);
  assert.equal(response.headers.get('content-type'), 'text/html; charset=utf-8');
  assert.equal(await response.text(), html('Bad Request'));
  for (const path of ['/outbox/', '/notify']) {
    response = await f.get(path);
    assert.equal(response.status, 404);
    assert.equal(await response.text(), html('Cannot GET ' + path));
  }
  response = await f.post({}, 'application/json', '/outbox/x');
  assert.equal(response.status, 404);
  assert.equal(await response.text(), html('Cannot POST /outbox/x'));
  assert.equal(f.db.counters.size, 0);
});

test('20 per hour; rejected requests do not enter outbox', async (t) => {
  const f = await fixture(t);
  for (let i = 1; i <= 22; i++) {
    const response = await f.post({ account: 'x', kind: 'statement_ready' });
    assert.equal(response.status, i <= 20 ? 202 : 429);
    if (i > 20) assert.equal(await response.text(), '{"error":"rate limited"}');
  }
  assert.equal((await (await f.get('/outbox/x')).json()).length, 20);
  assert.deepEqual(f.db.expirations, [['notify:rate:x', 3600]]);
});

test('store failures produce the legacy 503 body', async (t) => {
  for (const command of ['incr', 'expire', 'lPush', 'lRange']) {
    const db = new FakeRedis();
    db[command] = async () => { throw new Error('offline'); };
    const f = await fixture(t, db);
    const response = command === 'lRange' ? await f.get('/outbox/x') :
      await f.post({ account: 'x', kind: 'statement_ready' });
    assert.equal(response.status, 503);
    assert.equal(await response.text(), '{"error":"store unavailable"}');
  }
});

test('outbox reads only the newest 50 rows', async (t) => {
  const f = await fixture(t);
  f.db.outboxes.set('notify:outbox:x', Array.from({ length: 60 }, (_, i) => JSON.stringify({ text: i })));
  const rows = await (await f.get('/outbox/x')).json();
  assert.equal(rows.length, 50);
  assert.equal(rows[49].text, 49);
});
