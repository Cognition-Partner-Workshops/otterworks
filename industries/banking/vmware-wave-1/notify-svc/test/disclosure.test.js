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

function service(rows = []) {
  const routes = {};
  const values = new Map();
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
    console: { log() {}, error() {} }
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
