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

## Account reference secrets

Statements and notifications require `BANK_ACCOUNT_REFERENCE_SECRET` in the
server environment (at least 32 characters). Provision it once per application
using a cryptographically random value, for example `openssl rand -hex 32`,
and retain it in the deployment's secret manager across restarts and replicas.
Never put its value in source control, images, browser configuration or logs.
Inject it into the Tomcat and PM2 process environments through the deployment's
protected secret configuration; restart the processes after provisioning.
Statements also accepts the server-side JVM property
`bank.account.reference.secret`, which takes precedence over the environment.
Missing or short secrets reject reference generation; notify-svc rejects startup.
There is no unkeyed fallback or automatically regenerated ephemeral key.

Links use HMAC-SHA256, not account-number hashes. Statement lookup recomputes the
HMAC over account candidates; notification lookup uses Redis mappings and verifies
the HMAC with the current key. Keep the secret stable to keep links resolvable.
Rotating it, or upgrading from the old unkeyed references, invalidates old links;
refresh the account list or retrieve the outbox by its original account input to
obtain new links. Legacy Redis mappings are not accepted as a bypass. References
are routing identifiers, not substitutes for authentication and authorization.

## Cloud resources

A replatforming run uses ECR repositories `otterworks/bank-<app>` and namespaces `bank-w1-<run>-pr<n>` on `otterworks-dev`, deployed only by the pipeline's OIDC role. Every resource carries the run token (`run_token` tag on ECR, `demo/run-token` label on namespaces) and an expiry (`Expires` tag; `demo/expires-at` and `demo/expires-at-epoch` annotations, 72 hours by default).

```
make ecr RUN=<token>
make ns RUN=<token> PR=<n>
make destroy RUN=<token>   # removes both and exits non-zero if anything tagged with the token is left
```
