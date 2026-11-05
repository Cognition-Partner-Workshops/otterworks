# notify-svc on notify-01 and notify-02

Queues customer notifications (statement ready, card payment, low balance) for the SMS and push gateways to pick up.

- OS: Ubuntu 18.04, Node 12 from NodeSource, PM2 4.5 installed globally.
- Install: `/opt/notify-svc`, started with `pm2 start ecosystem.config.js --env production` and kept by `pm2 save`. `ecosystem.config.js` is the only record of how it runs: two cluster workers, a restart at 03:30, logs under `/var/log/notify`.
- Port: 3000, hard-coded in `src/server.js`.
- Redis: a local `redis-server` on each box, default port, no password. Rate-limit counters and the per-account outbox live there.
- API: `POST /notify` with `{"account", "kind", "fields"}`, `GET /outbox/<account>`.

In the wave stand-in, `make vm-up` serves it on http://localhost:8084/.

`NOTIFY_AUTHZ_FILE` points to a JSON file read once at startup: `{"principals":[{"name":"producer-name","role":"send","token_sha256":"<64 hex SHA-256 digest>","accounts":["HG611000001"]}]}`. Roles are `send` or `outbox`, one per principal; bearers are SHA-256 matched within their role. Each principal's accounts are explicit strict IDs: no wildcard; an empty list grants nothing. Duplicate hashes within a role are rejected.
Missing, unreadable or invalid configuration fails closed with 503 and a startup warning; a role without principals returns 503. Unknown bearers return 401; ungranted accounts return 403. Production principal/account mapping is an owner decision. Locally, `make notify-tokens` creates gitignored random smoke bearers and the read-only mounted hash/grant file before `make vm-up`.
