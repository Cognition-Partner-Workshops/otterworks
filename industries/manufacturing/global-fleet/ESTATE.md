# Global fleet estate

Two countries run the same company-car function on different stacks. The mainframe country keeps employees, vehicles, assignments, mileage claims and benefit periods in a CA IDMS database, maintained through ADS dialogs and paid out by a monthly COBOL batch. The Java country runs a Java 8 JSF 2.2 (Mojarra) portal on Tomcat 9 with JPA on PostgreSQL. Both estates are the before-state for a single global application, and the global application itself is outside this directory until the modernization work adds `fleet-service/` here and `frontend/fleet/` at the repository root.

## Layout

| Path | Contents |
|---|---|
| `mainframe/schema/` | `FLEETSCH.ddl` schema (areas, records, CALC keys, sets) and `FLEETSS1.ddl` subschemas |
| `mainframe/ads/` | five dialogs with their maps, premap and response processes, and the shared work record |
| `mainframe/batch/FLEBEN01.cbl` | monthly benefit run with IDMS DML |
| `mainframe/jcl/` | `FLEBEN01.jcl` for the run and `FLEUNLD.jcl` for the flat-file unload |
| `mainframe/copybooks/` | unload and output record layouts, with `LAYOUT.md` giving every offset |
| `mainframe/unload/` | flat-file unload of the whole database, the data the mainframe country hands over |
| `mainframe/holdout/` | twelve monthly pairs (`HP-202510` to `HP-202609`), each an `IN/` unload and the `OUT/` the benefit run produced, checksummed in `PAIRS.sha256` |
| `jsf-portal/` | Maven WAR for the Java country, built and run by its `Dockerfile` |
| `seed/jsf/` | `001_schema.sql` and `002_seed.sql` for the portal database |
| `source-browser/` | nginx image serving `mainframe/` read-only |
| `deploy/` | tenant wrapper and seed image |
| `terraform/gcp-fleet/` | Cloud Run and Cloud SQL for PostgreSQL for the global app on Google Cloud |

Copybooks and unloads follow `migration/source/copybooks/FIELD-DERIVATION.md` and `migration/source/unload/`: fixed-length records, ASCII text, `YYYYMMDD` dates with zeros for none, and `COMP-3` amounts. Each member record carries its owner's CALC key and db-key, since a flat file holds no sets.

## Countries

| | Mainframe country | Java country |
|---|---|---|
| Currency | GBP | EUR |
| Distance | miles | kilometres |
| Plate format | `AB12 CDE` | `M-AB 1234` |
| Employee ids | `E101xxxx` | `E100xxxx` |
| Screens | ADS dialogs `FLEMENU`, `FLEEMPI`, `FLEASGN`, `FLEMILE`, `FLERETN` | JSF pages `employees`, `request`, `assignment`, `mileage`, `statement`, `return` |
| Benefit run | `FLEBEN01` batch, one closed period per run | computed on the statement page |

## Seed

One generator with seed `20261027` and as-of date 2026-10-27 writes both the mainframe unloads and holdout pairs and the portal SQL seed, so the fifteen people who work in both countries appear in each with the same names. The mainframe unload holds 217 employees, 120 vehicles, 119 assignments and 1,511 mileage claims across 13 benefit periods. The portal seed holds 215 employees, 120 vehicles (40 of them pool cars), 111 assignments and 699 mileage claims. The generator stays outside the repository, and the committed files are its output.

The mainframe has no runtime here: there is no licensed IDMS in the sandbox, so the holdout pairs stand in for running `FLEBEN01`.

## Tenants

Both tenants run on the shared `otterworks-dev` cluster behind the shared ingress, with a namespace, quota, network policy, a database on the shared RDS instance and a `TENANT#<id>` control item. A run id names a pair of tokens, `<run>-before` and `<run>-after`, and every resource a tenant creates carries its token as the `demo/token` label, the ECR image tag and the control item's `token` attribute, with an expiry 72 hours out.

| Tenant | Token | Hosts | Workloads | Database |
|---|---|---|---|---|
| `gf-before` | `gf-r1027a-before` | `https://t-gf-before.demo.otterworks.app` (portal), `https://src-t-gf-before.demo.otterworks.app` (source browser) | `fleet-portal`, `source-browser` | `otterworks_gf_before` |
| `gf-after` | `gf-r1027a-after` | `https://t-gf-after.demo.otterworks.app` (`/` web, `/api` service) | `fleet-service`, `fleet-web` | `otterworks_gf_after` |

Images go to ECR as `otterworks/gf-fleet-portal`, `gf-source-browser`, `gf-seed`, `gf-fleet-service` and `gf-fleet-web`, tagged with the token.

## Commands

All commands run from the repository root with AWS credentials for the shared account. The DB admin password comes from `DB_PASSWORD` when set, otherwise from the platform secret the in-cluster runner uses.

```bash
# before tenant from this branch
industries/manufacturing/global-fleet/deploy/gf-tenant.sh up before

# after tenant: run on integration/global-fleet once fleet-service/ and frontend/fleet/ exist
git checkout integration/global-fleet && industries/manufacturing/global-fleet/deploy/gf-tenant.sh up after

# reload the fixed seed into both tenants and restart their workloads
industries/manufacturing/global-fleet/deploy/gf-tenant.sh reset

# destroy a run's tenants, then fail if anything still bears either token
industries/manufacturing/global-fleet/deploy/gf-tenant.sh down gf-r1027a
```

`up after` builds `industries/manufacturing/global-fleet/fleet-service/Dockerfile` and `frontend/fleet/Dockerfile` from the checked-out branch. The service is probed on `/actuator/health` and the web image on `/`, both on port 8080; `FLEET_SERVICE_HEALTH`, `FLEET_SERVICE_PORT`, `FLEET_WEB_HEALTH` and `FLEET_WEB_PORT` override them. The service reads `SPRING_DATASOURCE_URL`, `SPRING_DATASOURCE_USERNAME` and `SPRING_DATASOURCE_PASSWORD` from the tenant's `fleet-db` secret, and the database starts from the same seed as the before tenant.

`--run <id>` on `up` and `reset` targets another run (tenant ids become `<run>-before` and `<run>-after`), and `check <token>` lists what still bears a token. Each `up` and `reset` prints per-step timings and writes them under `~/.gf-timings/`. For each tenant, `down` calls `scripts/teardown-tenant.sh --token` to remove the namespace, database, ECR tags, DNS records, control item and any IRSA trust, and the script then lists every remaining resource bearing the token.
