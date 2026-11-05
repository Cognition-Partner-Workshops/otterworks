'use strict';

const express = require('express');
const redis = require('redis');
const crypto = require('crypto');
const { render, maskAccount } = require('./templates');

const PORT = 3000;
const LIMIT_PER_HOUR = 20;

function requireToken(envKey) {
  return (req, res, next) => {
    const expected = process.env[envKey];
    const supplied = (req.headers.authorization || '').replace(/^Bearer /, '');
    if (
      !expected ||
      !crypto.timingSafeEqual(
        crypto.createHash('sha256').update(expected).digest(),
        crypto.createHash('sha256').update(supplied).digest()
      )
    )
      return res.status(401).json({ error: 'service authentication required' });
    next();
  };
}

function createApp(db) {
  const app = express();
  app.use(express.json());

  app.post('/notify', requireToken('NOTIFY_SERVICE_TOKEN'), (req, res) => {
    const { account, kind, fields } = req.body || {};
    if (!account || !kind)
      return res.status(400).json({ error: 'account and kind are required' });
    let text;
    try {
      text = render(
        kind,
        Object.assign({}, fields, { account: maskAccount(account) })
      );
    } catch (e) {
      return res.status(400).json({ error: e.message });
    }
    const key = 'notify:rate:' + account;
    db.incr(key, (err, n) => {
      if (err) return res.status(503).json({ error: 'store unavailable' });
      if (n === 1) db.expire(key, 3600);
      if (n > LIMIT_PER_HOUR)
        return res.status(429).json({ error: 'rate limited' });
      const msg = JSON.stringify({
        account: maskAccount(account),
        kind,
        text,
        at: new Date().toISOString()
      });
      db.lpush('notify:outbox:' + account, msg, (e2) => {
        if (e2) return res.status(503).json({ error: 'store unavailable' });
        console.log('queued', kind, 'for', maskAccount(account));
        res.status(202).json({ queued: true, text });
      });
    });
  });

  app.get(
    '/outbox/:account',
    requireToken('NOTIFY_OUTBOX_TOKEN'),
    (req, res) => {
      db.lrange('notify:outbox:' + req.params.account, 0, 49, (err, rows) => {
        if (err) return res.status(503).json({ error: 'store unavailable' });
        res.json(rows.map((r) => JSON.parse(r)));
      });
    }
  );

  return app;
}

if (require.main === module) {
  const db = redis.createClient();
  db.on('error', (err) => console.error('redis error', err.message));
  createApp(db).listen(PORT, () =>
    console.log('notify-svc listening on', PORT)
  );
}
module.exports = { createApp };
