| Area | Calls | Result | Reason |
| --- | ---: | --- | --- |
| Health | 1 | accepted difference with reason | health names the backend that answers; it is meant to change at cutover |
| Month-end report (before writes) | 1 | accepted difference with reason | report source metadata names the engine (oracle -> postgresql); figures unchanged |
| Month-end report (after writes) | 1 | accepted difference with reason | report source metadata names the engine (oracle -> postgresql); figures unchanged |
| Month-end admin alias | 3 | accepted difference with reason | report source metadata names the engine (oracle -> postgresql); figures unchanged |
| Reconciliation report | 5 | accepted difference with reason | no migration baseline exists for an unseeded namespace, so it fails closed; on Oracle the estate is the baseline; after takeout the endpoint reconciles against it; post-migration checks recomputed from Postgres vs the Oracle figures in migration_baseline; report source metadata names the engine (oracle -> postgresql); figures unchanged; single migration-baseline: missing check instead of an empty baseline |
| Month-end, unseeded namespace | 1 | accepted difference with reason | report source metadata names the engine (oracle -> postgresql); figures unchanged |
| Plans | 2 | identical | 2 identical |
| Legacy HTML/JSON routes (/plans, /api/rating, /api/invoices, /api/dunning) | 31 | identical | 31 identical |
| /me | 28 | identical | 28 identical |
| Entitlement | 28 | identical | 28 identical |
| Usage | 28 | identical | 28 identical |
| Invoices and invoice lines | 47 | identical | 47 identical |
| Customer | 28 | identical | 28 identical |
| Admin overdue / dunning | 5 | identical | 5 identical |
| Internal usage ingest | 5 | identical | 5 identical |
| Plan change | 5 | accepted difference with reason | 503 detail names the engine; status code and error key unchanged |
| Rating finalize | 11 | identical | 11 identical |
| Invoice issue | 12 | identical | 12 identical |
| Dunning schedule / suspend | 3 | identical | 3 identical |
| Validation and auth errors | 3 | identical | 3 identical |

248 calls compared; 0 failed.
