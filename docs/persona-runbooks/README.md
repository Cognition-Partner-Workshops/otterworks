# Persona runbooks for Partner Demo - ViewOnly

One runbook per demo workstream, each written for the person who presents it. The audience sees the Devin console only, so every runbook ends with the sessions, pull requests and evidence a presenter opens from the sidebar of the persona that owns them. The three personas are AWS, Databricks and MongoDB. The former Cloud Engineer and Product Manager acts now live under AWS as one story: migrate, modernize, operate.

## Runbooks and personas

| Runbook | Persona (`runAs`) | Field Kit Area | Field Kit Identity | Delegation shape | Repository and branch |
|---|---|---|---|---|---|
| [AWS on-call: the parser page](aws-oncall-parser.md) | AWS | ISV and platform | AWS | Event driven | `otterworks`, release branch `demo-cw-release-1791186929-strict-parser`, harness on `devin/1791187037-cw-parser-fault` |
| [AWS modernization: legacy portal to Lambda](aws-legacy-portal.md) | AWS | ISV and platform | AWS | Scalable (one worker per bounded context) | `otterworks`, harness on `devin/1791186826-legacy-portal-serverless` |
| [AWS migration: Db2 retention history to RDS](aws-db2-rds.md) | AWS | ISV and platform | AWS | Well defined (staged job with a gate) | `otterworks`, `demo-cloud-worker` |
| [Databricks: Redshift marts in waves](databricks-redshift.md) | Databricks | ISV and platform | Databricks | Scalable (one child per unit) | `dbx-redshift-migration`, `migration-run-2` |
| [MongoDB: Oracle billing to Atlas](mongodb-billing.md) | MongoDB | ISV and platform | MongoDB | Repetitive (loader runs twice, recon gate) | `otterworks`, `devin/1791186817-mongodb-billing-run-prep` |

The user ids behind the personas, read from the session API on 2026-10-05:

| Persona | User id | Sign-in email |
|---|---|---|
| AWS | `user-094334530455473bb8c587d207307833` | `aws@fieldkit.devin.example` |
| Databricks | `user-c3478f949c414221a740236d07764e68` | `databricks@fieldkit.devin.example` |
| MongoDB | `user-5aded87015e641c5867bf64246f0e452` | `mongodb@fieldkit.devin.example` |

## Signing in as a persona

1. Open `https://fieldkit.devin.ai` and choose the Area and Identity from the table above. The form signs you into `https://partner-workshops.devinenterprise.com` as that persona.
2. Pick the organization `Partner Demo - ViewOnly` in the top left. The sidebar lists only the sessions this persona owns, which is the point: each runbook's sessions appear under the persona that ran them.
3. Every new session uses Fusion mode unless a runbook says otherwise. The Db2 migration run used Normal mode and the runbook says so.
4. To switch persona, sign out of the Devin web app first, then repeat step 1. A session started while signed in as the wrong persona stays owned by that persona.

## Rules every runbook shares

- `main` of `otterworks` is the golden app. Demo sessions push to their own branches and open pull requests against the branch the runbook names. Nobody merges a demo pull request during a demo, and the pull requests that remove a planted fault (the parser fix, the table startup check) stay open for good.
- Credentials are named by environment variable only. A runbook that needs a secret the org does not hold says so in its preflight and stops there.
- Each persona belongs to the uncapped `FieldKit` usage tier (Enterprise Settings, Usage policies). A persona left in the default tier has 100 ACU a cycle and every one of its sessions sleeps when that runs out; the legacy portal program spent that in about 40 minutes on 2026-10-05.
- Account numbers are redacted as `<account>` in every transcript that leaves the operator machine.
- Each runbook has a rerun log. Add a row every time you run it from a fresh session, with the date, the session link and what the runbook failed to say.

## Evidence

The build machine holds the operator evidence under `/home/ubuntu/prompts/aws-native/evidence/`: `aws/` for AWS reads (CloudTrail, alarm history, queue attributes, stack status), `devin/` for session metadata and sidebar screenshots per persona, `github/` for pull request and CI read-backs. The build report that indexes it is `/home/ubuntu/prompts/aws-native/report.md`. Each runbook names the files it relies on.
