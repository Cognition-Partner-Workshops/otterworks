# fx-report golden pages

Raw responses from the Perl/Apache stand-in (`fx-report/vm/Dockerfile`: Apache 2.4.69, Perl 5.40.1, CGI.pm 4.68)
and the rates files it read. The rewrite is tested against these files: same rates in, same HTML out.

Captured 2026-10-20 ~23:10 UTC from branch `devin/1792545000-bank-wave1` at `e42786c9e`. The container has no `TZ`
set, so it runs in UTC.

| File | Request | What it pins |
|---|---|---|
| `day-2026-10-14.html` | `?day=2026-10-14` | full table, every Change `n/a` (no `rates-2026-10-13.csv`) |
| `day-2026-10-15.html` | `?day=2026-10-15` | full table, Change against 2026-10-14 |
| `day-2026-10-16.html` | `?day=2026-10-16` | full table, Change against 2026-10-15 |
| `day-2026-10-17.html` | `?day=2026-10-17` | no file: "No rates file for this day yet." |
| `day-foo.html` | `?day=foo` | invalid date: business date blank (title `FX desk report `), no-file branch, still HTTP 200 |
| `no-day.html` | no `day` | defaults to yesterday in the container zone (UTC): captured as 2026-10-19, no file |
| `*.headers` | same | status line and headers (`200 OK`, `Content-Type: text/html; charset=utf-8`; no `Cache-Control`/`Expires` in the stand-in) |
| `rates/rates-2026-10-1{4,5,6}.csv` | | copied from `/mnt/rates-out` in report-01 (rates-batch spool), byte-identical (sha256 below) |

`no-day.html` depends on the capture date; compare it after substituting yesterday's date in the zone under test.
`Date` and `Server` in the `.headers` files change on every run and are not part of the contract.

## Commands

Run from `industries/banking/vmware-wave-1`. Docker Hub and Maven Central rate-limit this VM, so base images came
from `mirror.gcr.io` and Maven used the GCS mirror; neither changes what is built.

```sh
# base images through the mirror, tagged with the names the Dockerfiles use
for img in eclipse-temurin:11-jre httpd:2.4 maven:3.9-eclipse-temurin-11 node:12-bullseye python:2.7.18-slim python:3.12-slim postgres:16-alpine; do
  docker pull -q mirror.gcr.io/library/$img && docker tag mirror.gcr.io/library/$img docker.io/library/$img
done
docker pull -q mirror.gcr.io/library/maven@sha256:0f402712b7a469189cfea5ec69cdcadcb32b22aaf1ea62777ab925c3d8470175 \
  && docker tag mirror.gcr.io/library/maven@sha256:0f402712b7a469189cfea5ec69cdcadcb32b22aaf1ea62777ab925c3d8470175 docker.io/library/maven:3.9-eclipse-temurin-8
docker pull -q mirror.gcr.io/library/tomcat@sha256:e3ca75a4b11560bfb30894c3fa5d066ff0105e2e8e1ad183711df97606321e51 \
  && docker tag mirror.gcr.io/library/tomcat@sha256:e3ca75a4b11560bfb30894c3fa5d066ff0105e2e8e1ad183711df97606321e51 docker.io/library/tomcat:8.5-jre8

export MAVEN_MIRROR=https://maven-central.storage-download.googleapis.com/maven2/
make vm-build && make vm-up
# make vm-up output:
#   rates 2026-10-14: 5 pairs written to /var/spool/rates/out
#   rates 2026-10-15: 5 pairs written to /var/spool/rates/out
#   rates 2026-10-16: 5 pairs written to /var/spool/rates/out

G=fx-report/tests/golden; B=http://localhost:8086/fx/fx-report.cgi
mkdir -p $G/rates
for c in 2026-10-14 2026-10-15 2026-10-16 2026-10-17 foo; do
  curl -sS -D $G/day-$c.headers -o $G/day-$c.html "$B?day=$c"
done
curl -sS -D $G/no-day.headers -o $G/no-day.html "$B"
for d in 14 15 16; do docker compose -f vm/compose.yaml cp report-01:/mnt/rates-out/rates-2026-10-$d.csv $G/rates/; done

# what "yesterday" was in the container when no-day.html was taken
docker compose -f vm/compose.yaml exec -T report-01 date -d yesterday +%F   # 2026-10-19
```

`day=foo` also writes three warnings to Apache's error log (`docker compose -f vm/compose.yaml logs report-01`):

```
Use of uninitialized value $d in subtraction (-) at /var/www/fx-report/cgi-bin/fx-report.cgi line 16.
Use of uninitialized value $m in subtraction (-) at /var/www/fx-report/cgi-bin/fx-report.cgi line 16.
Use of uninitialized value $y in subtraction (-) at /var/www/fx-report/cgi-bin/fx-report.cgi line 16.
```

## Checksums

```
9d0060355c52c01282c3e16113cf44743122defa65c91ab01ed3ad77cce40a6a  day-2026-10-14.html
7327597a4538a5fda05a806ac8cdab493dda878fa636124cabbf6b6e06de973a  day-2026-10-15.html
2b047e1623d86683deadb9ad072ed0e646639a1acd84b2b6da9923910e5539d3  day-2026-10-16.html
8d7aa0f4e2ee2e4618106b6d5212c462d5d29a824627a43c9c5dcdb972deb5f2  day-2026-10-17.html
0ac0f3b21dcebde2057698fa01e11ff3651bb6f556300cbc583914e5016769f4  day-foo.html
dfadf5b531e39fe0857fa993e0466e6ffab2459dc8fee3c8b2f1b44f665e27a4  no-day.html
58c7b41354bdee7810fd80521cc5ebd2b92828a85aa21fec088b2574c093690d  rates/rates-2026-10-14.csv
e2746bf958143e87a41d126866b583d1d97d7365282d6ca17d190c2579262861  rates/rates-2026-10-15.csv
0bcf20da1ebabfc06420cc0688a9eaa23d149d31e2b06f55f01291beabd4bc2b  rates/rates-2026-10-16.csv
```

The rates files hash the same inside report-01 (`sha256sum /mnt/rates-out/rates-2026-10-1{4,5,6}.csv`).

## Behaviour the rewrite must keep

From `cgi-bin/fx-report.cgi` and `lib/FxReport/Rates.pm`, and visible in the pages above:

- pairs sorted by name; Close and Average mid printed verbatim from the CSV (`0.949120`, `161.955945`);
- Range is `high - low` printed `%.5f`; Change is `(close - prev_close) / prev_close * 100` printed `%+.3f%%`,
  `n/a` when the pair is missing from the previous calendar day's file;
- a `day` not matching `^\d{4}-\d\d-\d\d$` becomes the empty string, which looks up `rates-.csv` and shows the
  no-file branch with HTTP 200;
- the header line shows `REMOTE_USER` or `unknown` (always `unknown` here: the stand-in has no auth);
- the HTML is CGI.pm's XHTML 1.0 Transitional wrapper, rows separated by `\n`, no trailing newline after `</html>`.
