'use strict';

const express = require('express');
const redis = require('redis');
const { render, maskAccount } = require('./templates');

const PORT = Number(process.env.PORT) || 3000;
const LIMIT_PER_HOUR = 20;
const HEALTH_TIMEOUT_MS = 1000;

function redisOptions() {
  const opts = {};
  if (process.env.REDIS_PASSWORD) opts.password = process.env.REDIS_PASSWORD;
  if (process.env.REDIS_TLS === 'true') opts.tls = {};
  return opts;
}

const db = redis.createClient(process.env.REDIS_URL || 'redis://127.0.0.1:6379', redisOptions());
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
  db.lrange('notify:outbox:' + req.params.account, 0, 49, (err, rows) => {
    if (err) return res.status(503).json({ error: 'store unavailable' });
    res.json(rows.map((r) => JSON.parse(r)));
  });
});

app.get('/health', (req, res) => {
  if (!db.connected) return res.status(503).json({ status: 'redis unavailable' });
  let done = false;
  const timer = setTimeout(() => {
    done = true;
    res.status(503).json({ status: 'redis unavailable' });
  }, HEALTH_TIMEOUT_MS);
  db.ping((err) => {
    if (done) return;
    clearTimeout(timer);
    if (err) return res.status(503).json({ status: 'redis unavailable' });
    res.json({ status: 'ok' });
  });
});

const server = app.listen(PORT, () => console.log('notify-svc listening on', PORT));

process.on('SIGTERM', () => {
  console.log('notify-svc stopping');
  server.close(() => db.quit(() => process.exit(0)));
  setTimeout(() => process.exit(0), 10000).unref();
});
