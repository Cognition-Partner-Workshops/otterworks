'use strict';

const assert = require('assert');
const { render, maskAccount } = require('../src/templates');

assert.strictEqual(maskAccount('HG611000001'), '****0001');
assert.strictEqual(
  render('card_payment', { amount: '12.40', account: '****0001', merchant: 'Corner Cafe' }),
  'Card payment of 12.40 on ****0001 at Corner Cafe.'
);
assert.throws(() => render('card_payment', { account: 'x' }), /missing field: amount/);
assert.throws(() => render('nope', {}), /unknown notification kind/);

const fs = require('fs');
const vm = require('vm');
const routes = {};
const stored = [];
const app = {
  use() {},
  post(path, handler) { routes[path] = handler; },
  get(path, handler) { routes[path] = handler; },
  listen() {}
};
function express() { return app; }
express.json = () => () => {};
const db = {
  on() {},
  incr(key, cb) { cb(null, 1); },
  expire() {},
  lpush(key, msg, cb) { stored.push(msg); cb(null); },
  lrange(key, start, stop, cb) { cb(null, stored); }
};
vm.runInNewContext(fs.readFileSync(require.resolve('../src/server'), 'utf8'), {
  require(name) {
    if (name === 'express') return express;
    if (name === 'redis') return { createClient: () => db };
    return require('../src/templates');
  },
  console: { log() {} }
});
let response;
const res = { status() { return this; }, json(value) { response = value; } };
routes['/notify']({ body: { account: 'HG611000001', kind: 'statement_ready', fields: {} } }, res);
assert.strictEqual(response.text, 'Your statement for ****0001 is ready to view.');
assert.strictEqual(JSON.parse(stored[0]).account, 'HG611000001', 'internal queue keeps its identifier');
routes['/outbox/:account']({ params: { account: 'HG611000001' } }, res);
assert.strictEqual(response[0].account, '****0001', 'outbox masks customer-visible account');
assert.strictEqual(response[0].text, 'Your statement for ****0001 is ready to view.');
for (const [kind, fields] of [
  ['statement_ready', {}],
  ['card_payment', { amount: '12.40', merchant: 'Corner Cafe' }],
  ['low_balance', { threshold: '50.00' }]
]) {
  const text = render(kind, Object.assign({}, fields, { account: 'HG611000001' }));
  assert(text.includes('****0001'), kind + ' masks at the rendering boundary');
  assert(!text.includes('HG611000001'));
}
console.log('templates and notification routes: all assertions passed');
