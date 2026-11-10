# Talk track

## Opening

Your billing warehouse has run on SQL Server since 2016. It has 25 stored procedures, 12 SSIS packages, a SQL Agent schedule and a cron file the team has stopped editing, and 30 reports read from it every morning. Moving it to Snowflake usually means a team rewriting procedures for a quarter and then arguing about whether the numbers match. Today Devin does the rewrite in parallel, and a parity gate decides when each piece is done.

## Legacy estate

Here's the estate as the team left it. The procedures carry their change history in the header comments, with names and dates going back to 2016. Seven of them are already in Snowflake as dbt models, and the ledger shows those seven passing against SQL Server row for row. The other 18 are pending.

## Plan and fan-out

I hand the whole migration to one Devin session, which reads the estate, writes the plan and sorts the 18 procedures into waves by what each one reads. Then it starts a separate Devin for each procedure in the first wave, eight at once, each on its own machine with SQL Server and its own connection to Snowflake.

## One worker

The worker in this session owns `rate_overage`, the procedure that bills storage overage. It wrote the dbt model, ran the same nightly job on both warehouses for the 15th and compared every row. The first try diverged on 41 tenants. SQL Server says 40 gigabytes and Snowflake says 40.64, because the old code divides two integers and T-SQL drops the fraction. Your invoices have always billed whole gigabytes, so Devin matched the legacy rule and wrote down why. The unit passes on the 15th and on month-end.

## Evidence

Every pull request arrives with the ledger rows for its unit and the dbt test results. Nobody merges on trust. The gate exits 0 only when every unit passes or carries a written explanation that a person approved.

## Cutover

The last wave replaces the SQL Agent jobs and the cron entry with a Snowflake task graph, then the cutover stops the SQL Server replay and points the reports at Snowflake. The ledger in Snowsight is the record of what ran, viewed by a read-only user.

## Close

You've watched 18 procedures move to Snowflake, each one checked against the system it replaces. The session list shows what each Devin did and what it cost, so you can price the next warehouse before you start it.
