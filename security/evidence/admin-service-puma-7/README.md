# admin-service: Puma 7.2.1

Independent conservative update from demo-ciso 449e5f7ae. Only Puma changes in the lockfile,
6.6.1 to 7.2.1. The Gemfile pins the smallest fixed release exactly; the initially tried
open constraint '~> 7.2', '>= 7.2.1' resolved to 7.2.2, so it was narrowed to honor the
smallest-version requirement. Rails remains 7.1.6 and Ruby remains 3.3.
No app defaults, production configuration, policies, Dockerfile or schema changed.

## Exposure and compatibility

Puma CVE-2026-47736 and CVE-2026-47737 (both HIGH) disappear. Trivy's
`~> 7.2.1, >= 8.0.2` fixed-version string describes alternatives across major lines,
not a requirement to install 8.x: the 7.2.1 image has zero Puma findings.
No Puma 8 assessment is needed. Installed-package scans do not prove exploit reachability;
other Rails and dependency risks remain. Local images do not prove deployed ECR state.

Read the installed puma-7.2.1/History.md, especially 7.0.0 and 7.2.1.
The gem has no separate UPGRADE-7.0.md file. The changelog records:
- Ruby minimum 3.0 (Ruby 3.3 is supported).
- max_keep_alive default 999; persistent_timeout default 65 seconds.
- Response headers lowercase; HTTP_VERSION omitted for Rack >3.1.
- preload_app! default in clustered mode; renamed callback hooks; hooks require blocks.
- Internal Config clamp requirement and removal of Runner ruby_engine.
- 7.2.1 hardens PROXY protocol parsing.

config/puma.rb uses only threads, worker_timeout, port, environment, pidfile and
plugin :tmp_restart. None uses removed hooks/options. No workers or WEB_CONCURRENCY
were configured: both images booted single mode, min/max threads 5.
Dockerfile CMD remains rails db:migrate followed by rails server -b 0.0.0.0 -p 8089,
which works with Puma 7.2.1. Lowercase headers are observable but semantically equivalent.

## Verification

CI commands with Ruby 3.3 and PostgreSQL 15, RAILS_ENV=test:
```text
Finished in 1.83 seconds (files took 1.37 seconds to load)
120 examples, 0 failures
Randomized with seed 60234
7.1.6
```
The last line is the successful test Rails runner.
Warnings concern Rails 7.1 secrets deprecation and Rack's unprocessable_entity alias;
no new failure or defaults migration was required.

Both baseline and after production runners exit 1 at the same planted line:
```text
/app/config/environments/production.rb:8:in `block in <main>': undefined method `logger' for module ActiveSupport::TaggedLogging (NoMethodError)
  config.logger = ActiveSupport::TaggedLogging.logger($stdout)
```

Both images were started using the unchanged Dockerfile CMD, RAILS_ENV=test and
DATABASE_URL pointing to postgres:15. GET /health maps to HealthController#show
and actually executes SELECT 1. The baseline and after each returned:
```text
HTTP/1.1 200 OK
{"status":"healthy","service":"admin-service","version":"1.0.0","database":"connected",...}
```
Recorded baseline timestamp: 2026-11-13T14:26:43Z; after: 2026-11-13T14:26:44Z.
Boot logs:
```text
baseline: Puma version: 6.6.1 ("Return to Forever")
after:    Puma version: 7.2.1 ("On The Corner")
both:     Listening on http://0.0.0.0:8089
```

## Scan results

Trivy 0.71.0, frozen vulnerability DB v2 UpdatedAt
2026-11-13T12:56:33.451543713Z; --skip-db-update; no ignores.
The baseline scan from this same unchanged DB is reused.
JSON retains every finding with IDs, installed/fixed versions, severity, status and package path.
Counts include CVE/GHSA aliases without deduplication.

| Image | Total | Critical | High | Medium | Low | Unknown | Ruby | Debian |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 532 | 4 | 145 | 195 | 180 | 8 | 105 | 427 |
| Puma 7.2.1 | 530 | 4 | 143 | 195 | 180 | 8 | 103 | 427 |

Node package findings zero in both.

Baseline admin-base:demo-ciso:
`sha256:faf793c1a317af41a9fe40bc4463768f7d2cc0f591d7d0e5d15717152992bae3`
After admin-after:puma7:
`sha256:ec2bcd2e495d6b550718b5d5d19e80170c781a514505ba039fa23b1e4cbb8615`

Baseline Gemfile/lock hashes were previously verified against origin/demo-ciso.
No Ruby or Debian base change is part of this branch.

## Reproduction

```sh
# Clean demo-ciso worktree:
docker build -t admin-base:demo-ciso services/admin-service
# This branch:
docker run --rm -v "$PWD/services/admin-service:/app" -w /app ruby:3.3 bundle update puma --conservative
docker build -t admin-after:puma7 services/admin-service
# Reuse frozen DB; do not download/update it:
for image in admin-base:demo-ciso admin-after:puma7; do
  /home/ubuntu/bin/trivy image --cache-dir ~/.cache/trivy-rails72 --skip-db-update \
    --scanners vuln --ignorefile /dev/null --severity UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL \
    --format json "$image" > "${image//:/-}.json"
done
docker network create puma-test
docker run -d --name puma-pg --network puma-test -e POSTGRES_USER=otterworks \
  -e POSTGRES_PASSWORD=otterworks -e POSTGRES_DB=admin_service_test postgres:15
# Wait for pg_isready.
docker run --rm --network puma-test -v "$PWD/services/admin-service:/src:ro" \
  -e DATABASE_HOST=puma-pg -e DATABASE_PORT=5432 -e DATABASE_USER=otterworks \
  -e DATABASE_PASSWORD=otterworks -e RAILS_ENV=test ruby:3.3 bash -c \
  'set -e; cp -r /src /app; cd /app; bundle install -j4 --quiet; bundle exec rails db:schema:load; bundle exec rspec; bundle exec rails runner "puts Rails.version"'
docker run -d --name puma-base-server --network puma-test -p 127.0.0.1:18089:8089 \
  -e RAILS_ENV=test -e DATABASE_HOST=puma-pg \
  -e DATABASE_URL=postgresql://otterworks:otterworks@puma-pg/admin_service_test admin-base:demo-ciso
docker run -d --name puma-after-server --network puma-test -p 127.0.0.1:18090:8089 \
  -e RAILS_ENV=test -e DATABASE_HOST=puma-pg \
  -e DATABASE_URL=postgresql://otterworks:otterworks@puma-pg/admin_service_test admin-after:puma7
curl --retry 8 --retry-connrefused --retry-delay 1 -i http://127.0.0.1:18089/health
curl --retry 8 --retry-connrefused --retry-delay 1 -i http://127.0.0.1:18090/health
for image in admin-base:demo-ciso admin-after:puma7; do
  docker run --rm -e RAILS_ENV=production "$image" bundle exec rails runner 'puts Rails.version'
done
```

## Remaining Ruby findings

Puma: none. Other installed Ruby findings (exact IDs/fixed versions in JSON):

| Package / installed | Findings | Reported fixes |
|---|---:|---|
| actionmailbox 7.1.6 | 2 | 8.1.4.1, 8.0.5.2; ~> 8.0.5, >= 8.0.5.2, >= 8.1.4.1 |
| actionpack 7.1.6 | 12 | 8.1.4.1, 8.0.5.2; ~> 8.0.5, >= 8.0.5.2, >= 8.1.4.1 |
| actionview 7.1.6 | 9 | 8.1.4.1, 8.0.5.2; ~> 7.2.3, >= 7.2.3.1, ~> 8.0.4, >= 8.0.4.1, >= 8.1.2.1; ~> 8.0.5, >= 8.0.5.2, >= 8.1.4.1 |
| activestorage 7.1.6 | 18 | 8.1.4.1, 8.0.5.2; ~> 7.2.3, >= 7.2.3.1, ~> 8.0.4, >= 8.0.4.1, >= 8.1.2.1; ~> 8.0.5, >= 8.0.5.2, >= 8.1.4.1; ~> 7.2.3, >= 7.2.3.2, ~> 8.0.5, >= 8.0.5.1, >= 8.1.3.1 |
| activesupport 7.1.6 | 5 | 8.1.4.1, 8.0.5.2; ~> 7.2.3, >= 7.2.3.1, ~> 8.0.4, >= 8.0.4.1, >= 8.1.2.1; ~> 8.0.5, >= 8.0.5.2, >= 8.1.4.1 |
| crass 1.0.6 | 5 | >= 1.0.7; >= 1.0.8 |
| loofah 2.25.1 | 13 | 2.25.3; >= 2.25.2; >= 2.25.3 |
| mail 2.9.0 | 1 | >= 2.9.1 |
| msgpack 1.8.0 | 2 | 1.8.7; >= 1.8.2 |
| net-imap 0.4.25 | 3 | ~> 0.5.15, >= 0.6.4.1 |
| net-imap 0.6.4 | 3 | ~> 0.5.15, >= 0.6.4.1 |
| nokogiri 1.19.3 | 15 | >= 1.19.4; 1.19.5; >= 1.19.5 |
| rack 3.2.6 | 8 | 2.2.25, 3.1.23, 3.2.8; ~> 2.2.25, ~> 3.1.23, >= 3.2.8; 3.1.23, 3.2.8; ~> 3.1.23, >= 3.2.8 |
| rails-html-sanitizer 1.7.0 | 3 | >= 1.7.1; >= 1.7.2 |
| websocket-driver 0.8.0 | 4 | >= 0.8.1; >= 0.8.2 |
