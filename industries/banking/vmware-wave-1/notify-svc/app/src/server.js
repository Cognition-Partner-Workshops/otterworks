'use strict';

const express = require('express');
const { createClient } = require('redis');
const { render, maskAccount } = require('./templates');

function within(promise, milliseconds) {
  let timer;
  return Promise.race([
    promise,
    new Promise((resolve, reject) => {
      timer = setTimeout(() => reject(new Error('store timeout')), milliseconds);
    })
  ]).finally(() => clearTimeout(timer));
}

function createApp(db) {
  const app = express();
  app.use(express.json());

  app.get('/health', async (req, res) => {
    try {
      if (await within(db.ping(), 1000) !== 'PONG') throw new Error('store unavailable');
      res.json({ status: 'ok' });
    } catch (err) {
      res.status(503).json({ status: 'unavailable' });
    }
  });

  app.post('/notify', async (req, res) => {
    const { account, kind, fields } = req.body || {};
    if (!account || !kind) return res.status(400).json({ error: 'account and kind are required' });
    let text;
    try {
      text = render(kind, Object.assign({}, fields, { account: maskAccount(account) }));
    } catch (e) {
      return res.status(400).json({ error: e.message });
    }
    try {
      const key = 'notify:rate:' + account;
      const n = await db.incr(key);
      if (n === 1) await db.expire(key, 3600);
      if (n > 20) return res.status(429).json({ error: 'rate limited' });
      const msg = JSON.stringify({ account, kind, text, at: new Date().toISOString() });
      await db.lPush('notify:outbox:' + account, msg);
      console.log('queued', kind, 'for', maskAccount(account));
      res.status(202).json({ queued: true, text });
    } catch (err) {
      res.status(503).json({ error: 'store unavailable' });
    }
  });

  app.get('/outbox/:account', async (req, res) => {
    try {
      const rows = await db.lRange('notify:outbox:' + req.params.account, 0, 49);
      res.json(rows.map((row) => JSON.parse(row)));
    } catch (err) {
      res.status(503).json({ error: 'store unavailable' });
    }
  });
  return app;
}

function start() {
  const db = createClient({
    url: process.env.REDIS_URL || 'redis://localhost:6379',
    password: process.env.REDIS_PASSWORD || undefined,
    disableOfflineQueue: true,
    socket: { connectTimeout: 1000, reconnectStrategy: () => 500 }
  });
  db.on('error', (err) => console.error('redis error', err.message));
  db.connect().catch((err) => console.error('redis error', err.message));
  const server = createApp(db).listen(process.env.PORT || 8080,
    () => console.log('notify-svc listening on', process.env.PORT || 8080));
  process.once('SIGTERM', async () => {
    const deadline = setTimeout(() => process.exit(0), 5000);
    server.closeIdleConnections();
    await new Promise((resolve) => server.close(resolve));
    try {
      if (db.isReady) await within(db.quit(), 1000);
      else if (db.isOpen) await db.disconnect();
    } catch (err) {
      if (db.isOpen) await db.disconnect();
    }
    clearTimeout(deadline);
    process.exit(0);
  });
}

if (require.main === module) start();
module.exports = { createApp };
