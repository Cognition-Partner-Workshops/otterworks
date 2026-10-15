---
name: persona-demo-portfolio
description: >
  Browser and API helpers for building and tending a persona demo portfolio in
  the Partner Demo ViewOnly organization: sign the box's Chrome into Field Kit,
  open the Devin webapp as a persona (area and identity), read the persona's
  sidebar, press approval cards, answer a session as the persona, rename
  sessions from the header, and list or archive sessions through /v3. Used by
  the `!build_technologist_demo` playbook; nothing here touches application code.
---

# Persona demo portfolio helpers

A presenter signs in as one Field Kit persona and walks a customer through a
collection of finished sessions. Everything the audience sees belongs to that
persona, so the builder has to act as the persona too: approve its cards, answer
its questions, set its titles. These scripts do that from the Chrome already
running on the box, through CDP, with no password and no API key in the browser.

## Setup

1. `FIELD_KIT_AUTH_URL` (the Field Kit magic link) and `DEVIN_ENTERPRISE_API_KEY`
   come from the session secrets. Never print either.
2. Playwright: the scripts look in `PLAYWRIGHT_DIR`, then a global `playwright`,
   then `/home/ubuntu/repos/field-kit/node_modules/playwright`. On a box with
   none of those, `npm i playwright` in any scratch directory and point
   `PLAYWRIGHT_DIR` at it. Chrome is already running with CDP on
   `http://localhost:29229` (`CDP_URL` overrides).
3. `node scripts/fk_login.js` once per machine. It opens the magic link in the
   main Chrome profile and reports how many Field Kit cookies it holds. When the
   link page says the key is invalid or revoked, paste the same URL into the
   access key box on `fieldkit.devin.ai/sso.html`; that sets the same cookie.

## Personas

The SSO form has two native selects, area first, then identity. Known pairs:

| Area | Identity | Portfolio |
| --- | --- | --- |
| `Product, leadership and partner` | `Pre-Sales Solution Architect` | general partner, PR #1846 |
| `ISV and platform` | `AWS` | AWS, Databricks, MongoDB, PR #1826 |
| `Engineering` | `Legacy Modernization Engineer` | modernization, PR #1907 |

Read the option list on an open authorize page before trusting a new pair: the
form folds catalog groups into domains and the names differ from the catalog.
The first SSO login of a new identity creates a user with no organization; add it
as a Member through `POST /v3/enterprise/organizations/{org}/members/users/{user_id}`
and move it to the uncapped usage tier before launching anything.

## Scripts

All of them take `<area> <identity>` first and sign in inside an isolated
browser context, so three personas can run side by side without logging each
other out.

| Script | Purpose |
| --- | --- |
| `fk_login.js` | sign the main profile into Field Kit (once) |
| `sidebar.js <area> <identity> [out.png]` | print the sessions in the persona's sidebar, with a screenshot |
| `approve_cards.js <area> <identity> <id>...` | press Approve, Add to automation, Run now, Allow for this session, Confirm |
| `say.js <area> <identity> <id> "<text>"` | answer a session's question as the persona |
| `rename.js <area> <identity> plan.json` | rename sessions from the header; `plan.json` maps 32-character ids to titles |
| `sessions.py --org-name ViewOnly [--owner user-...]` | list a persona's sessions from `/v3`; `--session`, `--archive` for one |

`persona_page.js` is the shared login; import it for anything new.

## Titles

Two to five words that name the takeaway, the way a colleague labels a sticky
note: `Refactor`, `Fix a long-red job`, `One CVE, many instances`,
`Oracle out, 37 orphans`. No sentences, no PR numbers, no restating the
assignment (the prompt already says it). Rename from the header as the persona,
never by posting a message to the session or through the API: the message stays
in the agent's timeline and the title reads as the service account's work.
Workflow and board children keep their generated names.

## Rules

- Demo sessions belong to the persona; a session created by the builder or the
  service account is invisible to the audience's sidebar and cannot be re-owned.
- Approval cards accept only a member of the organization, so the persona presses
  them; the requester never has to.
- Messaging a session costs its attention. Read `/v3` and the sidebar first.
- Archive through `sessions.py --archive` only after the requester has seen the
  list with a reason per row.
- Nothing merges; demo PRs and guide PRs stay open for review.
