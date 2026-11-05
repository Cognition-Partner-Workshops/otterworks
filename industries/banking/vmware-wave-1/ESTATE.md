# Wave 1 estate

Six applications that run on VMs today, each with the files that keep it running there. They are the input for a replatforming wave onto the shared EKS cluster and the platform standards under `platform/standards/` on `main`.

| App | What it does | Runtime on the VM | VM stand-in |
| --- | --- | --- | --- |
| `statements-web` | customer statements pages | Java 8 WAR on Tomcat 8.5 | http://localhost:8081/statements/accounts |
| `rates-batch` | nightly reference FX rates | Java 11 JAR from cron | `make vm-rates` |
| `branch-locator` | find a branch | Python 2.7 Flask under systemd | http://localhost:8083/ |
| `notify-svc` | customer notification queue | Node 12 under PM2 with local Redis | http://localhost:8084/notify |
| `kyc-docs` | identity document intake | Spring Boot 2.3 with its own TLS | https://localhost:8085/documents/HG611000001 |
| `fx-report` | FX desk morning report | Perl CGI behind Apache | http://localhost:8086/fx/fx-report.cgi |

Each app folder has its source, its tests, `HOST.md` (how the VM runs it) and `vm/` (the host files and a Dockerfile that stands in for the VM). `complexity-manifest.json` lists what each app expects from its host and where that lives in the code.

## Shared data

`data/seed.sql` holds 24 synthetic accounts, their statement lines and six branches. `data/rates/in/` holds three days of hourly ticks for five currency pairs. The VM stand-ins and the replatformed apps load the same files, so a before and after comparison shows the same rows.

## Running it

```
make vm-build      # build the stand-in images (set MAVEN_MIRROR to use a Maven Central mirror)
make vm-up         # start them, then run rates-batch for the three tick days
make vm-smoke      # one request per app
make reset         # stop and drop the volumes
```

## Cloud resources

A replatforming run uses shared ECR repositories `otterworks/bank-<app>` and run-owned namespaces `bank-w1-<run>-pr<n>` on `otterworks-dev`, deployed only by the pipeline's OIDC role. Namespaces carry the `demo/run-token` label and the `demo/expires-at` and `demo/expires-at-epoch` annotations (72 hours by default). ECR repositories belong to the platform, not the creating run: new repositories carry only the project tag, with no run token or expiry. Existing repositories may still have legacy run tags; those tags never authorize run teardown to delete a shared repository.

```
make ecr RUN=<token>
make ns RUN=<token> PR=<n>
make destroy RUN=<token>   # removes run namespaces, retaining all shared ECR repositories
```

`destroy` still exits non-zero if run namespaces or non-ECR resources tagged with the run token remain. Shared repository deletion and legacy tag maintenance require a separate platform-owner procedure after checking all consumers; neither is part of run teardown.

The command-mock regression suite runs without cloud access or inherited credentials:

```
python3 -m unittest discover -s industries/banking/vmware-wave-1 -p test_resource_ownership.py -v
```
