'use strict';

const express = require('express');
const redis = require('redis');
const crypto = require('crypto');
const { render, maskAccount } = require('./templates');

const PORT = 3000;
const LIMIT_PER_HOUR = 20;

const ACCOUNT = /^[A-Z]{2}[0-9]{6,32}(?![\s\S])/;

function createApp(db) {
const app = express();
app.use(express.json());

function authorize(name) {
  if (!process.env[name]) console.warn('notify auth not configured: ' + name);
  return (req, res, next) => {
    const token = process.env[name];
    if (!token) return res.status(503).json({ error: 'notify auth not configured' });
    const expected = Buffer.from('Bearer ' + token);
    const actual = Buffer.from(req.get('Authorization') || '');
    if (actual.length !== expected.length || !crypto.timingSafeEqual(actual, expected)) {
      return res.set('WWW-Authenticate', 'Bearer').status(401).json({ error: 'unauthorized' });
    }
    next();
  };
}

app.post('/notify', authorize('NOTIFY_SEND_TOKEN'), (req, res) => {
  const { account, kind, fields } = req.body || {};
  if (!account || !kind) return res.status(400).json({ error: 'account and kind are required' });
  if (typeof account !== 'string' || !ACCOUNT.test(account)) return res.status(400).json({ error: 'invalid account' });
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

app.get('/outbox/:account', authorize('NOTIFY_OUTBOX_TOKEN'), (req, res) => {
  if (!ACCOUNT.test(req.params.account)) return res.status(400).json({ error: 'invalid account' });
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
  createApp(db).listen(PORT, () => console.log('notify-svc listening on', PORT));
}

module.exports = { createApp };
