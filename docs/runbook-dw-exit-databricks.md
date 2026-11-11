# Databricks warehouse and ETL exit runbook (short version)

The full runbook, the presenter guide and the session links live in the Field Kit packet `golden-core-otterworks-databricks` (Devin-Samples/field-kit, `data/packets/golden-core-otterworks-databricks.json`, runbook at `content/bronze/golden-core-otterworks-databricks.md`). This file gives the short version for anyone working on the `demo-databricks-dw-exit` branch.

## Scope

Run token `dbx-d1111` moved the OtterWorks estate off a Teradata warehouse, 20 PowerCenter mappings and 30 Spark jobs onto Databricks. Thirteen golden sessions in the `EXT - Core - OtterWorks` organization are owned by the Databricks Field Kit persona. Every pull request targets `demo-databricks-dw-exit`: 12 are merged there, 19 stay open as evidence, and none target `main`.

## Storyline

| Chapter | Golden session | Result to repeat |
|---|---|---|
| Billing parity nobody trusts | Billing to Delta, proven parity | Seven Teradata gaps failed first on live Delta and passed after the fix (#2766, merged). |
| Finance readers nobody mapped | Finance readers move to Databricks; Finance notebook on a Windows machine | Eight contracts green, two readers ready to retire; the Windows notebook matched 4 of 4 queries. |
| A PowerCenter licence renewing every year | PowerCenter to Databricks, parallel workers; PowerCenter audit mappings, bounded tickets | 11 of 12 mappings green, 9 of 20 still on PowerCenter; the Migrations board paused at its forecast. |
| Thirty Spark jobs under a crontab | Spark jobs move to serverless | 15 of 30 jobs green, 15 red with a cause, job DBUs pending. |
| An estate nobody has counted | Assess the warehouse estate | 277 objects, 25 unread in 90 days, one hidden finance reader (#2744, merged). |
| An overnight landing feed change | Schema drift repaired without prompting, plus three automation sessions | Drift check failed then passed, and a second backfill changed nothing. |
| Old credentials left behind | Databricks estate full security scan; SonarQube findings to engineering work | 25 native findings and 181 imported SonarQube findings, with fixes opened from both. |

## Ten-minute path

1. Billing to Delta, proven parity: scroll to the seven-row gap table.
2. Finance readers move to Databricks: show the parity board in the final message.
3. Schema drift repaired without prompting: play the recording, then open the session the drift alert started.

The Field Kit runbook holds the sentence to say at each stop and the thirty-minute path.

## Known limits

The Databricks warehouse, catalog objects, jobs, run token and the five `DATABRICKS_*` organization settings are torn down after the run. Live Databricks evidence lives in the recordings and the saved session messages, and a replay needs a fresh run token. The retirement gate, the licence counter, 15 Spark jobs and 169 untriaged SonarQube findings stay red by design.
