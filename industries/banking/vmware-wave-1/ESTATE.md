# Wave 1 estate

Six applications that run on VMs today, each with the files that keep it running there. They are the input for a replatforming wave onto local Kubernetes using the standards under `platform/standards/`.

| App | What it does | Runtime on the VM | VM stand-in |
| --- | --- | --- | --- |
| `statements-web` | customer statements pages | Java 8 WAR on Tomcat 8.5 | http://localhost:8081/statements/accounts |
| `rates-batch` | nightly reference FX rates | Java 11 JAR from cron | `make vm-rates` |
| `branch-locator` | find a branch | Python 2.7 Flask under systemd | http://localhost:8083/ |
| `notify-svc` | customer notification queue | Node 12 under PM2 with local Redis | http://localhost:8084/notify |
| `kyc-docs` | identity document intake | Spring Boot 2.3 with its own TLS | https://localhost:8085/documents/HG611000001 |
| `fx-report` | FX desk morning report | Perl CGI behind Apache | http://localhost:8086/fx/fx-report.cgi |

Each app folder has its source, tests, `HOST.md` (host configuration) and `vm/` (host files and a stand-in Dockerfile). The scorer's reference manifest is stored separately at `demos/app/bank-wave1-complexity-manifest.json`. Assessment and application workers must exclude `demos/` from their scope.

## Shared data

`data/seed.sql` holds 24 synthetic accounts, their statement lines and six branches. `data/rates/in/` holds three days of hourly ticks for five currency pairs. The VM stand-ins and the replatformed apps load the same files, so a before and after comparison shows the same rows.

## Running it

```
make vm-build      # build the stand-in images (set MAVEN_MIRROR to use a Maven Central mirror)
make vm-up         # start them, then run rates-batch for the three tick days
make vm-smoke      # one request per app
make reset         # stop and drop the volumes
```

Set a unique `COMPOSE_PROJECT_NAME` per run. `parity/run.py` compares independent VM and kind endpoints on the same seed data; `parity/README.md` lists the commands and comparison depths.

The local gate uses kind on GitHub-hosted runners. Cloud deployment is disabled in the wave caller.

## Existing cloud targets

The Makefile retains `ecr`, `ns` and `destroy` for separately approved cloud runs. Local-only runs must leave `BANK_W1_EKS` unset, keep `eks_deploy` false and avoid cloud creation targets.
