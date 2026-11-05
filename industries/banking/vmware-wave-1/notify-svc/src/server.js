'use strict';

const express = require('express');
const redis = require('redis');
const { createHmac } = require('crypto');
const { render, maskAccount } = require('./templates');

const PORT = 3000;
const LIMIT_PER_HOUR = 20;
const referenceSecret = process.env.BANK_ACCOUNT_REFERENCE_SECRET;
if (!referenceSecret || referenceSecret.length < 32) {
  throw new Error('BANK_ACCOUNT_REFERENCE_SECRET must contain at least 32 characters');
}

function referenceFor(account) {
  return createHmac('sha256', referenceSecret).update(String(account)).digest('hex');
}

const db = redis.createClient();
db.on('error', (err) => console.error('redis error', err.message));

const app = express();
app.use(express.json());

app.post('/notify', (req, res) => {
  const { account, kind, fields } = req.body || {};
  if (!account || !kind) return res.status(400).json({ error: 'account and kind are required' });
  let text;
  try {
    text = render(kind, Object.assign({}, fields, { account }));
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

app.get('/outbox/:account', (req, res) => {
  function read(account) {
    db.lrange('notify:outbox:' + account, 0, 49, (err, rows) => {
      if (err) return res.status(503).json({ error: 'store unavailable' });
      if (!rows.length) return res.json([]);
      const reference = referenceFor(account);
      db.set('notify:reference:' + reference, account, (mappingError) => {
        if (mappingError) return res.status(503).json({ error: 'store unavailable' });
        try {
          res.json(rows.map((r) => {
            const msg = JSON.parse(r);
            const original = String(msg.account);
            msg.text = String(msg.text).split(original).join(maskAccount(original));
            msg.outboxUrl = '/outbox/' + reference;
            msg.account = maskAccount(original);
            return msg;
          }));
        } catch (error) {
          res.status(500).json({ error: 'outbox unavailable' });
        }
      });
    });
  }
  if (/^[a-f0-9]{64}$/.test(req.params.account)) {
    db.get('notify:reference:' + req.params.account, (err, account) => {
      if (err) return res.status(503).json({ error: 'store unavailable' });
      if (!account || referenceFor(account) !== req.params.account) return res.status(404).json({ error: 'outbox not found' });
      read(account);
    });
  } else {
    read(req.params.account);
  }
});

app.listen(PORT, () => console.log('notify-svc listening on', PORT));
