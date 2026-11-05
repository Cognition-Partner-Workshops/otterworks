'use strict';

// INCR and the window expiry run as one script, so a counter can never be
// left without a TTL, and a counter already stuck without one gets it back.
const RATE_SCRIPT = [
  "local n = redis.call('INCR', KEYS[1])",
  "if redis.call('TTL', KEYS[1]) < 0 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end",
  'return n'
].join('\n');

function countRequest(db, key, windowSeconds, cb) {
  db.eval(RATE_SCRIPT, 1, key, windowSeconds, cb);
}

function pushOutbox(db, key, msg, maxEntries, ttlSeconds, cb) {
  db.multi()
    .lpush(key, msg)
    .ltrim(key, 0, maxEntries - 1)
    .expire(key, ttlSeconds)
    .exec((err, replies) => {
      if (err) return cb(err);
      const failed = (replies || []).find((r) => r instanceof Error);
      cb(failed || null);
    });
}

module.exports = { countRequest, pushOutbox };
