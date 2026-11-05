'use strict';
const assert = require('assert');
const http = require('http');
const { createApp } = require('../src/server');

async function main() {
  process.env.NOTIFY_SERVICE_TOKEN = 'test-onboarding-service-token';
  process.env.NOTIFY_OUTBOX_TOKEN = 'test-gateway-consumer-token';
  const messages = [];
  const db = {
    incr: (_key, cb) => cb(null, 1),
    expire: () => {},
    lpush: (_key, msg, cb) => {
      messages.push(msg);
      cb(null);
    },
    lrange: (_key, _start, _end, cb) => cb(null, messages)
  };
  const server = createApp(db).listen(0, '127.0.0.1');
  await new Promise((resolve) => server.once('listening', resolve));
  function request(method, path, token) {
    return new Promise((resolve, reject) => {
      const req = http.request(
        {
          hostname: '127.0.0.1',
          port: server.address().port,
          method,
          path,
          headers: {
            'Content-Type': 'application/json',
            Authorization: 'Bearer ' + (token || '')
          }
        },
        (res) => {
          let body = '';
          res.on('data', (chunk) => {
            body += chunk;
          });
          res.on('end', () => resolve({ status: res.statusCode, body }));
        }
      );
      req.on('error', reject);
      req.end(
        method === 'POST'
          ? JSON.stringify({
              account: 'HG611000001',
              kind: 'statement_ready',
              fields: { month: 'March' }
            })
          : undefined
      );
    });
  }
  try {
    assert.strictEqual((await request('POST', '/notify')).status, 401);
    assert.strictEqual(
      (await request('GET', '/outbox/HG611000001')).status,
      401
    );
    assert.strictEqual(
      (
        await request(
          'GET',
          '/outbox/HG611000001',
          process.env.NOTIFY_SERVICE_TOKEN
        )
      ).status,
      401
    );
    assert.strictEqual(
      (await request('POST', '/notify', process.env.NOTIFY_SERVICE_TOKEN))
        .status,
      202
    );
    assert.strictEqual(JSON.parse(messages[0]).account, '****0001');
    assert.strictEqual(
      (
        await request(
          'GET',
          '/outbox/HG611000001',
          process.env.NOTIFY_OUTBOX_TOKEN
        )
      ).status,
      200
    );
    delete process.env.NOTIFY_SERVICE_TOKEN;
    assert.strictEqual(
      (await request('POST', '/notify', 'anything')).status,
      401
    );
    console.log('access: 7 assertions passed');
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
}
main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
