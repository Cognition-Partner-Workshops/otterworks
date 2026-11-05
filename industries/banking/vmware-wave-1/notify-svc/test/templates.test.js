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
for (const merchant of ['https://example.invalid', 'www.example.invalid', 'a\nb', '\x00', '\x7f', '\x85', 'x'.repeat(65), {}, [], true, Infinity, NaN]) {
  assert.throws(() => render('card_payment', { amount: 12, account: '****0001', merchant }), /invalid field: merchant/);
}
assert.strictEqual(render('low_balance', { account: '****0001', threshold: 0 }), 'The balance on ****0001 is below 0.');
assert.strictEqual(render('card_payment', { amount: 12, account: '****0001', merchant: 'x'.repeat(64) }), 'Card payment of 12 on ****0001 at ' + 'x'.repeat(64) + '.');
assert.strictEqual(render('statement_ready', { account: '****0001', ignored: {} }), 'Your statement for ****0001 is ready to view.');
console.log('templates: validation and existing behavior passed');
