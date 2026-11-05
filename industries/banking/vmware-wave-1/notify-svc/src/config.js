'use strict';

function readConfig(env) {
  const port = env.PORT === undefined ? 3000 : Number(env.PORT);
  if (!/^\d+$/.test(String(env.PORT === undefined ? 3000 : env.PORT)) ||
      !Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error('PORT must be an integer between 1 and 65535');
  }
  const redisUrl = env.REDIS_URL === undefined ? 'redis://127.0.0.1:6379' : env.REDIS_URL;
  let url;
  try { url = new URL(redisUrl); } catch (err) { throw new Error('Invalid REDIS_URL'); }
  if (!['redis:', 'rediss:'].includes(url.protocol) || !url.hostname || url.username || url.password) {
    throw new Error('REDIS_URL must use redis or rediss without credentials');
  }
  if (env.REDIS_PASSWORD === '') throw new Error('REDIS_PASSWORD must not be empty');
  return { port, redisUrl, redisPassword: env.REDIS_PASSWORD };
}

module.exports = { readConfig };
