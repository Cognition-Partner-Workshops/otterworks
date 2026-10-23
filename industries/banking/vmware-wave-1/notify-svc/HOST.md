# notify-svc on notify-01 and notify-02

Queues customer notifications (statement ready, card payment, low balance) for the SMS and push gateways to pick up.

- OS: Ubuntu 18.04, Node 12 from NodeSource, PM2 4.5 installed globally.
- Install: `/opt/notify-svc`, started with `pm2 start ecosystem.config.js --env production` and kept by `pm2 save`. `ecosystem.config.js` is the only record of how it runs: two cluster workers, a restart at 03:30, logs under `/var/log/notify`.
- Port: 3000, hard-coded in `src/server.js`.
- Redis: a local `redis-server` on each box, default port, no password. Rate-limit counters and the per-account outbox live there.
- API: `POST /notify` with `{"account", "kind", "fields"}`, `GET /outbox/<account>`.

In the wave stand-in, `make vm-up` serves it on http://localhost:8084/.
