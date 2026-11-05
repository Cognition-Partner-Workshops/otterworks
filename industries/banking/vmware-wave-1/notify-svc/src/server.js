'use strict';

const express = require('express');
const redis = require('redis');
const crypto = require('crypto');
const { render, maskAccount } = require('./templates');
const { ACCOUNT, validateAuthz, loadAuthz } = require('./authz');

const PORT = 3000;
const LIMIT_PER_HOUR = 20;

function createApp(db, authz) {
try {
  authz = validateAuthz(authz);
} catch (err) {
  authz = null;
}
if (!authz || ['send', 'outbox'].some(role => !authz.principals.some(p => p.role === role))) {
  console.warn('notify auth not configured');
}
const app = express();

function authorize(role) {
  const principals = authz ? authz.principals.filter(p => p.role === role) : [];
  return (req, res, next) => {
    if (!principals.length) return res.status(503).json({ error: 'notify auth not configured' });
    const bearer = /^Bearer ([^\s]+)$/.exec(req.get('Authorization') || '');
    const actual = crypto.createHash('sha256').update(bearer ? bearer[1] : '').digest();
    let principal;
    principals.forEach(p => {
      if (crypto.timingSafeEqual(actual, Buffer.from(p.token_sha256, 'hex')) && bearer) principal = p;
    });
    if (!principal) {
      return res.set('WWW-Authenticate', 'Bearer').status(401).json({ error: 'unauthorized' });
    }
    req.notifyPrincipal = principal;
    next();
  };
}

app.post('/notify', authorize('send'), express.json(), (req, res) => {
  const { account, kind, fields } = req.body || {};
  if (!account || !kind) return res.status(400).json({ error: 'account and kind are required' });
  if (typeof account !== 'string' || !ACCOUNT.test(account)) return res.status(400).json({ error: 'invalid account' });
  if (!req.notifyPrincipal.accounts.includes(account)) return res.status(403).json({ error: 'forbidden' });
  let text;
  try {
    text = render(kind, Object.assign({}, fields, { account: maskAccount(account) }));
  } catch (e) {
    return res.status(400).json({ error: e.message });
  }
  const key = 'notify:rate:' + account;
  db.incr(key, (err, n) => {
    if (err) return res.status(503).json({ error: 'store unavailable' });
    if (n === 1) db.expire(key, 3600);
    if (n > LIMIT_PER_HOUR) return res.status(429).json({ error: 'rate limited' });
    const msg = JSON.stringify({ account, kind, text, at: new Date().toISOString() });
    db.lpush('notify:outbox:' + account, msg, (e2) => {
      if (e2) return res.status(503).json({ error: 'store unavailable' });
      console.log('queued', kind, 'for', maskAccount(account));
      res.status(202).json({ queued: true, text });
    });
  });
});

app.get('/outbox/:account', authorize('outbox'), (req, res) => {
  if (!ACCOUNT.test(req.params.account)) return res.status(400).json({ error: 'invalid account' });
  if (!req.notifyPrincipal.accounts.includes(req.params.account)) return res.status(403).json({ error: 'forbidden' });
  db.lrange('notify:outbox:' + req.params.account, 0, 49, (err, rows) => {
    if (err) return res.status(503).json({ error: 'store unavailable' });
    res.json(rows.map((r) => JSON.parse(r)));
  });
});

return app;
}

if (require.main === module) {
  const db = redis.createClient();
  db.on('error', (err) => console.error('redis error', err.message));
  createApp(db, loadAuthz(process.env.NOTIFY_AUTHZ_FILE)).listen(PORT, () => console.log('notify-svc listening on', PORT));
}

module.exports = { createApp };
