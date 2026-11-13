# admin-service: Rails 7.2.3.1

Independent of the sibling image/meta-gem and gem-patch branches; based on demo-ciso 449e5f7ae.
The Rails meta-gem is retained and pinned to exactly 7.2.3.1. The unbounded example constraint
would currently resolve to 7.2.3.2, so the exact requested version is pinned.
Ruby remains 3.3 and the Dockerfile is unchanged. App defaults remain 7.1.
No application code, policies, production configuration or schema changed.

## Exposure and limits

This reduces known vulnerable gem findings; it does **not** clear all Rails CVEs.
The retained Rails meta-gem installs Active Storage and Action Mailbox as well as core Rails.
Trivy reports installed packages, not proof of reachable exploit paths. Some advisories appear
under both CVE and GHSA identifiers and the counts below do not deduplicate them.
Rails 7.2.3.1 still has critical Active Storage findings and high findings in core components;
many fixed versions in this DB require Rails 8.0.5.2 or 8.1.4.1.
CVE-2026-66066 has a 7.2.3.2 fix. Other gem patch remediation is intentionally independent.
Default Ruby gems are included: net-imap 0.4.25 remains visible to Trivy even though the
application lockfile selects 0.6.8.

These are local images only; they do not prove the deployed ECR image or tenant state.

## Images and scanner

Trivy 0.71.0; vulnerability DB v2 UpdatedAt 2026-11-13T12:56:33.451543713Z.
The DB was downloaded once to ~/.cache/trivy-rails72, then both scans used --skip-db-update.
Scans were serialized after an initial concurrent attempt encountered a cache lock; the
successful outputs below use the same unchanged DB.

Baseline admin-base:demo-ciso: `sha256:faf793c1a317af41a9fe40bc4463768f7d2cc0f591d7d0e5d15717152992bae3`
After admin-after:rails72: `sha256:40382dfaf7b950113240ef7777e9383b295c16f19f5b87fc1bed118a037041a7`

Reused baseline admin-service:baseline (faf793c1a317); its /app/Gemfile and Gemfile.lock
SHA256 values match origin/demo-ciso:
85b7b9ad07aa39388d2ac2450eb97dcdd88300ac666ba4e930360e2a0a55519a and
ae5a2b44aa2df0e67cfea9dd9fd2d2e68f84e4ed60f14b8984e98680159ec606.
Base ruby:3.3-slim image ID db3ad6dd68a886d51a187fb9bf486052f2976cdbe3b750169c25092aba1297fa.

| Image | Total | Critical | High | Medium | Low | Unknown | Ruby | Debian |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 532 | 4 | 145 | 195 | 180 | 8 | 105 | 427 |
| after | 515 | 2 | 140 | 186 | 179 | 8 | 88 | 427 |

Node package findings: zero in both. JSON is minimized to image identity, OS and every
finding's identifier, package, installed/fixed version, status, severity and package path.
No findings were filtered or ignored.

## Reproduction

From a clean demo-ciso worktree:
```sh
docker build -t admin-base:demo-ciso services/admin-service
# From this branch:
docker run --rm -v "$PWD/services/admin-service:/app" -w /app ruby:3.3 bundle update rails --conservative
docker build -t admin-after:rails72 services/admin-service
/home/ubuntu/bin/trivy image --download-db-only --cache-dir ~/.cache/trivy-rails72
for image in admin-base:demo-ciso admin-after:rails72; do
  /home/ubuntu/bin/trivy image --cache-dir ~/.cache/trivy-rails72 --skip-db-update \
    --scanners vuln --ignorefile /dev/null --severity UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL \
    --format json "$image" > "${image//:/-}.json"
done
docker network create rails72-test
docker run -d --name rails72-pg --network rails72-test \
  -e POSTGRES_USER=otterworks -e POSTGRES_PASSWORD=otterworks \
  -e POSTGRES_DB=admin_service_test postgres:15
# Wait for pg_isready before the suite.
docker run --rm --network rails72-test -v "$PWD/services/admin-service:/src:ro" \
  -e DATABASE_HOST=rails72-pg -e DATABASE_PORT=5432 -e DATABASE_USER=otterworks \
  -e DATABASE_PASSWORD=otterworks -e RAILS_ENV=test ruby:3.3 bash -c \
  'set -e; cp -r /src /app; cd /app; bundle install -j4 --quiet; bundle exec rails db:schema:load; bundle exec rspec; bundle exec rails runner "puts Rails.version"'
for image in admin-base:demo-ciso admin-after:rails72; do
  docker run --rm -e RAILS_ENV=production "$image" bundle exec rails runner 'puts Rails.version'
done
```

## Behavior checks

PostgreSQL 15, Ruby 3.3, same schema-load and RSpec commands as CI:
```text
Finished in 1.92 seconds (files took 1.35 seconds to load)
120 examples, 0 failures
Randomized with seed 43261
7.2.3.1
```
The test Rails runner exited zero. Both production image runners exited 1 at the
same intentionally planted error (not an earlier boot error):
```text
/app/config/environments/production.rb:8:in `block in <main>': undefined method `logger' for module ActiveSupport::TaggedLogging (NoMethodError)
  config.logger = ActiveSupport::TaggedLogging.logger($stdout)
```
Four Rack warnings originate from rspec-rails-6.1.5/lib/rspec/rails/matchers/have_http_status.rb:219:
`:unprocessable_entity` is deprecated in favor of `:unprocessable_content`.
The HTTP status remains 422 and the existing contracts pass; this is a future Rack naming
deprecation, not a failed Rails behavior contract. No defaults were migrated.

## Removed identifiers

Identifiers absent from the after image (global ID set difference; all are CVEs):
- CVE-2026-33168
- CVE-2026-33169
- CVE-2026-33170
- CVE-2026-33173
- CVE-2026-33174
- CVE-2026-33176
- CVE-2026-33195
- CVE-2026-33202
- CVE-2026-33658
- CVE-2026-54463
- CVE-2026-54464
- CVE-2026-54465
- CVE-2026-61666
- CVE-2026-63435

## Residual Ruby findings

Every residual Ruby finding is listed, including GHSA aliases. Fixed-version strings are
reported verbatim from Trivy, not a claim that an in-constraint fix exists.

| Package | Installed | ID | Severity | Fixed versions |
|---|---|---|---|---|
| actionmailbox | 7.2.3.1 | CVE-2026-126068 | LOW | 8.1.4.1, 8.0.5.2 |
| actionmailbox | 7.2.3.1 | GHSA-5957-c7qm-m469 | LOW | ~> 8.0.5, >= 8.0.5.2, >= 8.1.4.1 |
| actionpack | 7.2.3.1 | CVE-2026-126081 | HIGH | 8.1.4.1, 8.0.5.2 |
| actionpack | 7.2.3.1 | GHSA-wm3x-v3qw-4jh3 | HIGH | ~> 8.0.5, >= 8.0.5.2, >= 8.1.4.1 |
| actionpack | 7.2.3.1 | CVE-2026-126072 | MEDIUM | 8.1.4.1, 8.0.5.2 |
| actionpack | 7.2.3.1 | CVE-2026-126073 | MEDIUM | 8.1.4.1, 8.0.5.2 |
| actionpack | 7.2.3.1 | CVE-2026-126076 | MEDIUM | 8.1.4.1, 8.0.5.2 |
| actionpack | 7.2.3.1 | CVE-2026-126077 | MEDIUM | 8.1.4.1, 8.0.5.2 |
| actionpack | 7.2.3.1 | GHSA-2586-8ghr-69fj | MEDIUM | ~> 8.0.5, >= 8.0.5.2, >= 8.1.4.1 |
| actionpack | 7.2.3.1 | GHSA-r9jg-fmfx-2gv6 | MEDIUM | ~> 8.0.5, >= 8.0.5.2, >= 8.1.4.1 |
| actionpack | 7.2.3.1 | GHSA-rwvh-fw6r-pwvp | MEDIUM | ~> 8.0.5, >= 8.0.5.2, >= 8.1.4.1 |
| actionpack | 7.2.3.1 | GHSA-x6mj-8jx9-qhqv | MEDIUM | ~> 8.0.5, >= 8.0.5.2, >= 8.1.4.1 |
| actionpack | 7.2.3.1 | CVE-2026-126067 | LOW | 8.1.4.1, 8.0.5.2 |
| actionpack | 7.2.3.1 | GHSA-gmj8-hvj3-49mw | LOW | ~> 8.0.5, >= 8.0.5.2, >= 8.1.4.1 |
| actionview | 7.2.3.1 | CVE-2026-126069 | MEDIUM | 8.1.4.1, 8.0.5.2 |
| actionview | 7.2.3.1 | CVE-2026-126070 | MEDIUM | 8.1.4.1, 8.0.5.2 |
| actionview | 7.2.3.1 | CVE-2026-126078 | MEDIUM | 8.1.4.1, 8.0.5.2 |
| actionview | 7.2.3.1 | CVE-2026-126079 | MEDIUM | 8.1.4.1, 8.0.5.2 |
| actionview | 7.2.3.1 | GHSA-2p2f-4rq4-gjwc | MEDIUM | ~> 8.0.5, >= 8.0.5.2, >= 8.1.4.1 |
| actionview | 7.2.3.1 | GHSA-68p9-83h6-5wpj | MEDIUM | ~> 8.0.5, >= 8.0.5.2, >= 8.1.4.1 |
| actionview | 7.2.3.1 | GHSA-rq8q-p985-fjq7 | MEDIUM | ~> 8.0.5, >= 8.0.5.2, >= 8.1.4.1 |
| actionview | 7.2.3.1 | GHSA-v6rj-xm57-3p59 | MEDIUM | ~> 8.0.5, >= 8.0.5.2, >= 8.1.4.1 |
| activestorage | 7.2.3.1 | CVE-2026-122006 | CRITICAL | 8.1.4.1, 8.0.5.2 |
| activestorage | 7.2.3.1 | GHSA-f3w6-w445-fwh9 | CRITICAL | ~> 8.0.5, >= 8.0.5.2, >= 8.1.4.1 |
| activestorage | 7.2.3.1 | CVE-2026-126186 | HIGH | 8.1.4.1, 8.0.5.2 |
| activestorage | 7.2.3.1 | CVE-2026-66066 | HIGH | ~> 7.2.3, >= 7.2.3.2, ~> 8.0.5, >= 8.0.5.1, >= 8.1.3.1 |
| activestorage | 7.2.3.1 | GHSA-v924-7rp8-4mxh | HIGH | ~> 8.0.5, >= 8.0.5.2, >= 8.1.4.1 |
| activestorage | 7.2.3.1 | CVE-2026-126074 | MEDIUM | 8.1.4.1, 8.0.5.2 |
| activestorage | 7.2.3.1 | CVE-2026-126084 | MEDIUM | 8.1.4.1, 8.0.5.2 |
| activestorage | 7.2.3.1 | CVE-2026-126085 | MEDIUM | 8.1.4.1, 8.0.5.2 |
| activestorage | 7.2.3.1 | GHSA-3w93-6hmw-whh4 | MEDIUM | ~> 8.0.5, >= 8.0.5.2, >= 8.1.4.1 |
| activestorage | 7.2.3.1 | GHSA-hfr4-8rjc-97m2 | MEDIUM | ~> 8.0.5, >= 8.0.5.2, >= 8.1.4.1 |
| activestorage | 7.2.3.1 | GHSA-p2pm-g2h6-7j5j | MEDIUM | ~> 8.0.5, >= 8.0.5.2, >= 8.1.4.1 |
| activestorage | 7.2.3.1 | CVE-2026-126188 | LOW | 8.1.4.1, 8.0.5.2 |
| activestorage | 7.2.3.1 | GHSA-3f4q-8x5m-76v8 | LOW | ~> 8.0.5, >= 8.0.5.2, >= 8.1.4.1 |
| activesupport | 7.2.3.1 | CVE-2026-126080 | HIGH | 8.1.4.1, 8.0.5.2 |
| activesupport | 7.2.3.1 | GHSA-8474-xrp6-wh69 | HIGH | ~> 8.0.5, >= 8.0.5.2, >= 8.1.4.1 |
| crass | 1.0.6 | CVE-2026-61845 | HIGH | >= 1.0.7 |
| crass | 1.0.6 | CVE-2026-61847 | HIGH | >= 1.0.7 |
| crass | 1.0.6 | CVE-2026-116695 | MEDIUM | >= 1.0.8 |
| crass | 1.0.6 | CVE-2026-61846 | MEDIUM | >= 1.0.7 |
| crass | 1.0.6 | CVE-2026-61848 | MEDIUM | >= 1.0.7 |
| loofah | 2.25.1 | CVE-2026-126203 | MEDIUM | 2.25.3 |
| loofah | 2.25.1 | CVE-2026-126205 | MEDIUM | 2.25.3 |
| loofah | 2.25.1 | CVE-2026-126207 | MEDIUM | 2.25.3 |
| loofah | 2.25.1 | CVE-2026-126208 | MEDIUM | 2.25.3 |
| loofah | 2.25.1 | CVE-2026-126209 | MEDIUM | 2.25.3 |
| loofah | 2.25.1 | CVE-2026-73490 | MEDIUM | >= 2.25.2 |
| loofah | 2.25.1 | GHSA-345x-3rq2-jfrm | MEDIUM | >= 2.25.3 |
| loofah | 2.25.1 | GHSA-h6v6-rg66-fqj4 | MEDIUM | >= 2.25.3 |
| loofah | 2.25.1 | GHSA-m3x9-938q-5767 | MEDIUM | >= 2.25.3 |
| loofah | 2.25.1 | GHSA-mf2j-8f84-cc9q | MEDIUM | >= 2.25.3 |
| loofah | 2.25.1 | CVE-2026-73491 | LOW | >= 2.25.2 |
| loofah | 2.25.1 | GHSA-5qhf-9phg-95m2 | LOW | >= 2.25.2 |
| loofah | 2.25.1 | GHSA-p9wj-w8xq-vjx6 | UNKNOWN | >= 2.25.3 |
| msgpack | 1.8.0 | CVE-2026-126366 | HIGH | 1.8.7 |
| msgpack | 1.8.0 | CVE-2026-54522 | MEDIUM | >= 1.8.2 |
| net-imap | 0.4.25 | CVE-2026-47240 | MEDIUM | ~> 0.5.15, >= 0.6.4.1 |
| net-imap | 0.4.25 | CVE-2026-47242 | MEDIUM | ~> 0.5.15, >= 0.6.4.1 |
| net-imap | 0.4.25 | CVE-2026-47241 | LOW | ~> 0.5.15, >= 0.6.4.1 |
| nokogiri | 1.19.3 | GHSA-5prr-v3j2-97mh | MEDIUM | >= 1.19.4 |
| nokogiri | 1.19.3 | CVE-2026-126062 | LOW | 1.19.5 |
| nokogiri | 1.19.3 | CVE-2026-126063 | LOW | 1.19.5 |
| nokogiri | 1.19.3 | CVE-2026-126064 | LOW | 1.19.5 |
| nokogiri | 1.19.3 | GHSA-5v8h-3h3q-446p | LOW | >= 1.19.4 |
| nokogiri | 1.19.3 | GHSA-8678-w3jw-xfc2 | LOW | >= 1.19.4 |
| nokogiri | 1.19.3 | GHSA-9cv2-cfxc-v4v2 | LOW | >= 1.19.4 |
| nokogiri | 1.19.3 | GHSA-p67v-3w7g-wjg7 | LOW | >= 1.19.4 |
| nokogiri | 1.19.3 | GHSA-phwj-rprq-35pp | LOW | >= 1.19.4 |
| nokogiri | 1.19.3 | GHSA-v995-44v6-5fqm | LOW | >= 1.19.5 |
| nokogiri | 1.19.3 | GHSA-wfpw-mmfh-qq69 | LOW | >= 1.19.4 |
| nokogiri | 1.19.3 | GHSA-wjv4-x9w8-wm3h | LOW | >= 1.19.4 |
| nokogiri | 1.19.3 | GHSA-3w22-6jfg-527w | UNKNOWN | >= 1.19.5 |
| nokogiri | 1.19.3 | GHSA-4p39-36wj-23h4 | UNKNOWN | >= 1.19.5 |
| nokogiri | 1.19.3 | GHSA-g9g8-vgvw-g3vf | UNKNOWN | >= 1.19.4 |
| puma | 6.6.1 | CVE-2026-47736 | HIGH | ~> 7.2.1, >= 8.0.2 |
| puma | 6.6.1 | CVE-2026-47737 | HIGH | ~> 7.2.1, >= 8.0.2 |
| rack | 3.2.6 | CVE-2026-125111 | HIGH | 2.2.25, 3.1.23, 3.2.8 |
| rack | 3.2.6 | GHSA-5v64-555j-wjxm | HIGH | ~> 2.2.25, ~> 3.1.23, >= 3.2.8 |
| rack | 3.2.6 | CVE-2026-125109 | MEDIUM | 3.1.23, 3.2.8 |
| rack | 3.2.6 | CVE-2026-125110 | MEDIUM | 2.2.25, 3.1.23, 3.2.8 |
| rack | 3.2.6 | GHSA-2j8w-xcrc-x985 | MEDIUM | ~> 3.1.23, >= 3.2.8 |
| rack | 3.2.6 | GHSA-wvg4-6p58-3gh3 | MEDIUM | ~> 2.2.25, ~> 3.1.23, >= 3.2.8 |
| rack | 3.2.6 | CVE-2026-125108 | LOW | 2.2.25, 3.1.23, 3.2.8 |
| rack | 3.2.6 | GHSA-p8x9-v4hv-2w4g | LOW | ~> 2.2.25, ~> 3.1.23, >= 3.2.8 |
| rails-html-sanitizer | 1.7.0 | CVE-2026-73648 | MEDIUM | >= 1.7.1 |
| rails-html-sanitizer | 1.7.0 | GHSA-cpgf-5mjf-73p7 | MEDIUM | >= 1.7.2 |
| rails-html-sanitizer | 1.7.0 | GHSA-h7wh-q2qr-458c | MEDIUM | >= 1.7.2 |
