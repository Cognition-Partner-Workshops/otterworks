'use strict';

const TEMPLATES = {
  statement_ready: 'Your statement for {account} is ready to view.',
  card_payment: 'Card payment of {amount} on {account} at {merchant}.',
  low_balance: 'The balance on {account} is below {threshold}.'
};

function render(kind, fields) {
  const t = TEMPLATES[kind];
  if (!t) throw new Error('unknown notification kind: ' + kind);
  return t.replace(/\{(\w+)\}/g, (m, k) => {
    if (fields[k] === undefined || fields[k] === null) throw new Error('missing field: ' + k);
    return String(fields[k]);
  });
}

function maskAccount(account) {
  const s = String(account);
  return s.length <= 4 ? s : '****' + s.slice(-4);
}

module.exports = { TEMPLATES, render, maskAccount };
