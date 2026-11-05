'use strict';

// Needs a Redis server: REDIS_URL (default redis://127.0.0.1:6379).
// Uses its own key prefix and removes its keys when done.
const assert = require('assert');
const redis = require('redis');
const { countRequest, pushOutbox } = require('../src/store');

const db = redis.createClient(process.env.REDIS_URL || 'redis://127.0.0.1:6379');
const prefix = 'notify-test:' + process.pid + ':';
const p = (fn, ...args) => new Promise((resolve, reject) =>
  fn(...args, (err, v) => (err ? reject(err) : resolve(v))));
const cmd = (name, ...args) => p(db[name].bind(db), ...args);

async function main() {
  const rate = prefix + 'rate';
  assert.strictEqual(await p(countRequest, db, rate, 3600), 1);
  const ttl = await cmd('ttl', rate);
  assert.ok(ttl > 0 && ttl <= 3600, 'counter gets its window on the first request, ttl=' + ttl);
  assert.strictEqual(await p(countRequest, db, rate, 3600), 2);
  assert.ok((await cmd('ttl', rate)) <= ttl, 'later requests do not extend the window');

  const stuck = prefix + 'stuck';
  await cmd('set', stuck, '25');
  assert.strictEqual(await cmd('ttl', stuck), -1);
  assert.strictEqual(await p(countRequest, db, stuck, 3600), 26);
  assert.ok((await cmd('ttl', stuck)) > 0, 'a counter left without a TTL gets one back');

  const outbox = prefix + 'outbox';
  for (let i = 1; i <= 60; i++) await p(pushOutbox, db, outbox, 'm' + i, 50, 604800);
  assert.strictEqual(await cmd('llen', outbox), 50, 'outbox is trimmed to the cap');
  const rows = await cmd('lrange', outbox, 0, -1);
  assert.strictEqual(rows[0], 'm60', 'newest first');
  assert.strictEqual(rows[49], 'm11', 'oldest entries beyond the cap are dropped');
  const ottl = await cmd('ttl', outbox);
  assert.ok(ottl > 604000 && ottl <= 604800, 'outbox has a retention TTL, ttl=' + ottl);

  await assert.rejects(p(pushOutbox, db, rate, 'x', 50, 604800), /WRONGTYPE/,
    'a failed command inside the transaction is reported');

  console.log('store: 11 assertions passed');
}

main()
  .catch((e) => { console.error(e); process.exitCode = 1; })
  .finally(() => db.keys(prefix + '*', (e, keys) => {
    if (keys && keys.length) db.del(keys, () => db.quit()); else db.quit();
  }));
