'use strict';

const express = require('express');
const redis = require('redis');
const { render, maskAccount } = require('./templates');
const { countRequest, pushOutbox } = require('./store');

const PORT = 3000;
const LIMIT_PER_HOUR = 20;
const OUTBOX_MAX_ENTRIES = 50;
const OUTBOX_TTL_SECONDS = 7 * 24 * 3600;

const db = redis.createClient();
db.on('error', (err) => console.error('redis error', err.message));

const app = express();
app.use(express.json());

app.post('/notify', (req, res) => {
  const { account, kind, fields } = req.body || {};
  if (!account || !kind) return res.status(400).json({ error: 'account and kind are required' });
  let text;
  try {
    text = render(kind, Object.assign({}, fields, { account: maskAccount(account) }));
  } catch (e) {
    return res.status(400).json({ error: e.message });
  }
  const key = 'notify:rate:' + account;
  countRequest(db, key, 3600, (err, n) => {
    if (err) return res.status(503).json({ error: 'store unavailable' });
    if (n > LIMIT_PER_HOUR) return res.status(429).json({ error: 'rate limited' });
    const msg = JSON.stringify({ account, kind, text, at: new Date().toISOString() });
    pushOutbox(db, 'notify:outbox:' + account, msg, OUTBOX_MAX_ENTRIES, OUTBOX_TTL_SECONDS, (e2) => {
      if (e2) return res.status(503).json({ error: 'store unavailable' });
      console.log('queued', kind, 'for', maskAccount(account));
      res.status(202).json({ queued: true, text });
    });
  });
});

app.get('/outbox/:account', (req, res) => {
  db.lrange('notify:outbox:' + req.params.account, 0, OUTBOX_MAX_ENTRIES - 1, (err, rows) => {
    if (err) return res.status(503).json({ error: 'store unavailable' });
    res.json(rows.map((r) => JSON.parse(r)));
  });
});

app.listen(PORT, () => console.log('notify-svc listening on', PORT));
