# Rates batch side-by-side parity

Executed on 2026-11-05: **12 cases, 12 passed**, plus three input seed checks.

From the repository root:

```sh
bash industries/banking/vmware-wave-1/rates-batch/parity/run-parity.sh
```

The VM side used the original `demo-bank` rates-01 and report-01 Compose
stand-ins, before rebuilding the full VM stack from this branch. The original
rates image was `sha256:2629cf38e3c2412a1795542283e975e6ea26a207940ae11ba165e24306df4a1f`.
The container side created independent Jobs from `cronjob/rates-batch` in
`app-rates-batch` on kind cluster `w1-rates-batch`, using image
`599083837640.dkr.ecr.us-east-1.amazonaws.com/otterworks/bank-rates-batch:local`
(`sha256:2415d408e255e110c13b8483662d171176e936be3320f9becade4d96474cce90`).
Input and output object downloads use signed S3 GET requests through the
port-forwarded SeaweedFS S3 API, not the filer API.

## Time zone and normalisation

- Both VM services reported UTC with TZ unset. The second report container also
  leaves TZ unset. Container jobs use `TZ=Etc/UTC`, `BUSINESS_TZ=Etc/UTC`.
- Cases 4–6 replace only `/var/spool/rates/out` and `s3://bank-rates/out` with
  `<OUT>` in the stdout line.
- Case 7 replaces only `/var/spool/rates/in` and `s3://bank-rates/in` with `<IN>`
  in missing-ticks stderr; both exits are 1.
- Case 8 compares exit codes and the first exception line, not stack traces.
- Case 9 compares the usage line and requires exit 2.
- Cases 10–12 compare HTTP status, Content-Type and body bytes. No body
  normalisation is performed; Date and other headers are not compared.

## Input seed checks (local files equal S3 objects)

| Day | SHA-256 |
|---|---|
| 2026-10-14 | `fcae3c6e465ab8e8d9d8c4fc7cb5df624eb40d56bafcab1e8d3f6e5232ec9e8f` |
| 2026-10-15 | `4c8d5c220d0a3a1602ee3a6e8eae13617bcbd2337eb6cac5f5ba1c66aec108c8` |
| 2026-10-16 | `3370a21747f1b1d0f68bd99642cd8c4dc690454ad23eb373fa8daf533c99775e` |

Reference `data/seed.sql` SHA-256:
`d0a85dd227832fd10b71cbaebb9ee4efe0fc38e257293f0eb9be444cdf613756`.

## Output checks (VM equals container)

| Day | CSV SHA-256 | Report body SHA-256 |
|---|---|---|
| 2026-10-14 | `58c7b41354bdee7810fd80521cc5ebd2b92828a85aa21fec088b2574c093690d` | `9d0060355c52c01282c3e16113cf44743122defa65c91ab01ed3ad77cce40a6a` |
| 2026-10-15 | `e2746bf958143e87a41d126866b583d1d97d7365282d6ca17d190c2579262861` | `7327597a4538a5fda05a806ac8cdab493dda878fa636124cabbf6b6e06de973a` |
| 2026-10-16 | `0bcf20da1ebabfc06420cc0688a9eaa23d149d31e2b06f55f01291beabd4bc2b` | `2b047e1623d86683deadb9ad072ed0e646639a1acd84b2b6da9923910e5539d3` |

All six report responses were HTTP 200 with Content-Type
`text/html; charset=utf-8`. Full case values are in `results.tsv`. The three CSV
files and three report bodies for each side are retained in `out/vm/` and
`out/container/`. Other generated diagnostics are ignored by Git.

The script is rerunnable: it replaces its own Jobs and second report container,
and writes fresh evidence. The operator must provide the desired VM baseline;
after the full branch VM rebuild, it no longer represents the original image.

After parity passed, the complete branch VM estate passed:

```sh
cd industries/banking/vmware-wave-1
export DOCKER_BUILDKIT=0
export MAVEN_MIRROR=https://maven-central.storage-download.googleapis.com/maven2/
make vm-build && make vm-up && make vm-smoke
```

Smoke responses: statements-web 200, branch-locator 200, notify-svc 202,
kyc-docs 200, fx-report 200; all three rates output files were present.
