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
console.log('templates: 4 assertions passed');
