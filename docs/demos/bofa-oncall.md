# Document Vault on-call demo (10 min, `demo-bofa`)

One story: a production page gets fixed with no human prompt. The page comes
from the Bank of America-skinned Document Vault (`demo-bofa`, tenant `bofa`,
`t-bofa.demo.otterworks.app`). Alertmanager posts the firing alert to the
existing incident-responder Automation (`docs/incident-responder/automation.md`);
the session follows `.agents/skills/incident-responder/SKILL.md`. Nothing in this
demo is new except the tenant's values overlay
(`infrastructure/helm/tenant-values/bofa/document-service.yaml`).

## Rules

- One arm is one real page and one real Devin session. Arm once per demo; never
  re-arm "to be sure". Disarm when you finish.
- The slowness is real (the planted n-plus-one on `main`, which `demo-bofa`
  tracks). Never describe the cause on screen, in slides or in Slack: the point
  is that Devin finds it from telemetry. Say what a loan officer sees: "the document
  list takes over a second to load; request rate is flat".
- Never fix the flaw on `demo-bofa`. The responder's PR targets `demo-bofa` and
  stays open; merging it ends re-armability until it is reverted.
- The full fix takes longer than 10 minutes. The live part is the trigger; the
  middle is a pre-recorded run from the same tenant.
- Keep the concept banner on screen. Bank of America is not affiliated.

## Before the demo (same day)

1. `demo-bofa` deployed with the reskin and seeded vault (pushing the branch
   deploys it). Check the alert carries the branch:
   `kubectl -n otterworks-bofa get prometheusrule -o yaml | grep 'branch: demo-bofa'`.
   No label means the tenant was not deployed through the runner, and the
   responder stops instead of guessing; redeploy with
   `scripts/deploy-tenant.sh bofa --branch demo-bofa`.
2. Record one full run: `incident/tenant.sh arm bofa`, wait for the session,
   let it finish, `incident/tenant.sh disarm bofa`. Keep the session URL, the PR
   and its recording. Close the PR or leave it open; do not merge.
3. Have open: the vault logged in, the Automation page, the pre-recorded session
   and PR, Grafana.

## Run of show

| Time | Show | Say |
|---|---|---|
| 0:00 | The vault, document list | "Loan officers say the vault is slow." |
| 1:00 | Automation page: webhook trigger, no prompt | "Nobody assigns this. The page is the prompt." |
| 1:30 | `incident/tenant.sh arm bofa`; reload the list (slow); session appears ~90 s later | "That's the real alert, not a replay." |
| 2:30 | Pre-recorded session: three numbers from traces, local repro gate red, root cause file:line | "It reads telemetry before it reads code." |
| 5:00 | Fix (query, index, test), same load green, before/after table | "Proven with the same load, not a unit test." |
| 7:00 | The PR: screenshots, gate output, browser recording | "A reviewer merges this in a minute." |
| 9:00 | Automations list: CI failure, Jira label, weekly sweep | "Same pattern, any event." |

Disarm: `incident/tenant.sh disarm bofa`; the alerts resolve on their own.
