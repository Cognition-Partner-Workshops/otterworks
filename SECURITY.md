# Security Policy

## Supported versions

OtterWorks is not released as versioned packages. The `main` branch is the
golden app: every service image (`:main` tag) and the perpetual `t-main`
tenant are built from it, so it is the only line that receives security fixes.

| Branch / artifact                                   | Supported |
| --------------------------------------------------- | --------- |
| `main` and images built from it                     | Yes       |
| `workshop-<id>` / `demo-<id>` branches and tenants  | No — ephemeral variants derived from `main`; rebase or redeploy from `main` to pick up fixes |
| Tags and backup branches (e.g. `tp-*`, `*-backup`)  | No        |

## Intentional vulnerabilities

Parts of this repository are deliberately vulnerable so that security and
remediation labs have something to find. These are **not** in scope for
reports:

- Planted bugs on `main` documented in `AGENTS.md`.
- Findings accepted in the DAST baseline (`security/dast/baseline.json`) and
  the source-level findings registered for the functional-equivalence labs
  (`security/equivalence/`).
- The pinned dependency advisory in `security/deps/advisory.yaml`
  (CVE-2022-42889, `org.apache.commons:commons-text`).

If you are unsure whether something is planted, report it privately anyway
and say so.

## Reporting a vulnerability

Please **do not** open a public issue, pull request or discussion for a
security problem.

Report it privately through GitHub Security Advisories:

1. Go to the repository's **Security** tab.
2. Choose **Report a vulnerability**
   (<https://github.com/Cognition-Partner-Workshops/otterworks/security/advisories/new>).
3. Include the affected service or path (e.g. `services/file-service`), the
   branch or commit, reproduction steps or a proof of concept, and the impact
   you observed.

If you cannot use GitHub's private reporting, contact the code owners listed
in `.github/CODEOWNERS` directly and ask for a private channel. Never include
real credentials, tokens or customer data in a report.

## What to expect

- Acknowledgement within 3 business days.
- An initial assessment (accepted, planted/out of scope, or need more
  information) within 10 business days.
- Fixes land on `main` through a pull request; the advisory is published once
  the fix is merged and the `:main` images are rebuilt. Reporters are credited
  in the advisory unless they ask not to be.
