'use strict';
const assert = require('assert').strict;
const fs = require('fs');
const vm = require('vm');

let passed = 0;
let failed = 0;
function test(name, check) {
  try {
    check();
    passed++;
    console.log('ok - ' + name);
  } catch (error) {
    failed++;
    process.exitCode = 1;
    console.error('not ok - ' + name + '\n' + error.stack);
  }
}
process.on('exit', () => console.log('Disclosure tests: ' + passed + ' passed, ' + failed + ' failed'));

const referenceSecret = require('crypto').randomBytes(32).toString('hex');
function service(rows = [], secret = referenceSecret, values = new Map()) {
  const routes = {};
  const app = { use() {}, post: (path, handler) => { routes[path] = handler; },
    get: (path, handler) => { routes[path] = handler; }, listen() {} };
  const express = () => app;
  express.json = () => () => {};
  const db = { on() {}, incr: (key, cb) => cb(null, 1), expire() {},
    lpush: (key, msg, cb) => { rows.push(msg); cb(null); },
    lrange: (key, start, end, cb) => cb(null, rows),
    set: (key, value, cb) => { values.set(key, value); cb(null); },
    get: (key, cb) => cb(null, values.get(key)) };
  vm.runInNewContext(fs.readFileSync(require.resolve('../src/server'), 'utf8'), {
    require: name => name === 'express' ? express : name === 'redis' ? { createClient: () => db }
      : name === 'crypto' ? require('crypto') : require('../src/templates'),
    console: { log() {}, error() {} },
    process: { env: secret === null ? {} : { BANK_ACCOUNT_REFERENCE_SECRET: secret } }
  });
  const res = { code: 200, status(code) { this.code = code; return this; }, json(body) { this.body = body; } };
  return { routes, res, db, values };
}

test('unknown and empty outbox lookups create no Redis reference keys', () => {
  const { routes, res, db, values } = service();
  for (let n = 0; n < 100; n++) {
    routes['/outbox/:account']({ params: { account: 'missing-' + n } }, res);
    assert.equal(JSON.stringify(res.body), '[]');
  }
  assert.equal(values.size, 0, 'Empty lookups must not allocate persistent mappings');
  db.lrange = (key, start, end, cb) => cb(new Error('store failure'));
  routes['/outbox/:account']({ params: { account: 'missing-error' } }, res);
  assert.equal(res.code, 503);
  assert.equal(values.size, 0);
});

test('references are keyed, survive restart, and reject legacy dictionary hashes', () => {
  const account = 'HG611000001';
  const rows = [JSON.stringify({ account, text: 'Statement for ' + account })];
  const first = service(rows);
  first.routes['/outbox/:account']({ params: { account } }, first.res);
  const reference = first.res.body[0].outboxUrl.split('/').pop();
  const crypto = require('crypto');
  assert.equal(reference, crypto.createHmac('sha256', referenceSecret).update(account).digest('hex'));
  const restarted = service(rows, referenceSecret, first.values);
  restarted.routes['/outbox/:account']({ params: { account: reference } }, restarted.res);
  assert.equal(JSON.stringify(restarted.res.body), JSON.stringify(first.res.body));
  const rotated = service(rows, crypto.randomBytes(32).toString('hex'));
  rotated.routes['/outbox/:account']({ params: { account } }, rotated.res);
  assert.notEqual(rotated.res.body[0].outboxUrl, first.res.body[0].outboxUrl);
  const legacy = crypto.createHash('sha256').update(account).digest('hex');
  first.values.set('notify:reference:' + legacy, account);
  first.routes['/outbox/:account']({ params: { account: legacy } }, first.res);
  assert.equal(first.res.code, 404);
});

test('missing or short reference secrets fail closed', () => {
  assert.throws(() => service([], null), /BANK_ACCOUNT_REFERENCE_SECRET/);
  assert.throws(() => service([], 'short'), /BANK_ACCOUNT_REFERENCE_SECRET/);
});

test('outbox links and legacy text disclose no complete account, and links still work', () => {
  const account = 'HG611000001';
  const { routes, res } = service([JSON.stringify({ account, kind: 'statement_ready', text: 'Statement for ' + account })]);
  routes['/outbox/:account']({ params: { account } }, res);
  assert(!JSON.stringify(res.body).includes(account), 'Outbox response must not expose account in text or URLs');
  const first = JSON.stringify(res.body);
  routes['/outbox/:account']({ params: { account: res.body[0].outboxUrl.split('/').pop() } }, res);
  assert.equal(JSON.stringify(res.body), first);
});

test('notification kind errors do not echo accounts and template fields are masked', () => {
  const { routes, res } = service();
  routes['/notify']({ body: { account: 'HG611000001', kind: 'HG611000001', fields: {} } }, res);
  assert.equal(res.code, 400);
  assert(!JSON.stringify(res.body).includes('HG611000001'), 'Error must not echo an account-valued kind');
  routes['/notify']({ body: { account: 'HG611000001', kind: 'card_payment',
    fields: { amount: '12', merchant: 'Transfer HG611000001' } } }, res);
  assert(!res.body.text.includes('HG611000001'));
});

test('empty outboxes and store errors remain safe', () => {
  const { routes, res, db } = service();
  routes['/outbox/:account']({ params: { account: 'HG611000001' } }, res);
  assert.equal(JSON.stringify(res.body), '[]');
  db.lrange = (key, start, end, cb) => cb(new Error('HG611000001'));
  routes['/outbox/:account']({ params: { account: 'HG611000001' } }, res);
  assert.equal(res.code, 503);
  assert(!JSON.stringify(res.body).includes('HG611000001'));
});
