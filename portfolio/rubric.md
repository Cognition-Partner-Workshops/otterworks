# Platform standard for done

Each disposition in the rubric is defined by evidence. Retire needs no user traffic and a named plan for every remaining caller. Rehost needs a reason the code cannot change cheaply. Replatform needs a managed target for each stateful dependency and a named upgrade path for anything past end of life. Rearchitect needs clean seams and a parity corpus that can prove each port. An application that holds data whose deletion a person has to approve gets no disposition and goes to its owner.

A disposition is done when every claim behind it links to a file and line or a log query, and the scorecard counts it as found.

## Dispositions

`retire`, `rehost`, `replatform`, `rearchitect`, or `none` (no disposition, flagged for the owner).

## Report columns

`portfolio/assessment-report.csv` has one row per application in `portfolio/app-inventory.csv`, with these columns:

| Column | Meaning |
|---|---|
| `application` | The name from the inventory |
| `disposition` | One of the five values above |
| `questionnaire_disposition` | The inventory's answer, copied |
| `agrees_with_questionnaire` | `yes` or `no` |
| `caveat` | What has to happen first, or empty |
| `flag_owner` | The team that must decide, when the disposition is `none`, or empty |
| `evidence` | Semicolon-separated `path:line` links or log queries |

## Access logs

Ninety days of access logs per application sit under `s3://otterworks-data-lake-dev/appassess/<run token>/access-logs/<application>/`. The rows are synthetic and deterministic, written by `scripts/appassess/generate-access-logs.py`.
