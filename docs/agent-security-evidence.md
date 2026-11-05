# Agent reachability: observed evidence and remaining controls

**Scope:** One read-only examination on 2026-11-05 UTC from [this Devin session](https://partner-workshops.devinenterprise.com/sessions/332224df477f44f6865622e222f146eb), plus a tagged [second session](https://partner-workshops.devinenterprise.com/sessions/c7c1c5776d3e4b50b14534999b5e41e7) for a filesystem check. The only proposed repository change is this document and its screenshots, on a branch for a draft PR into `main`. No production service, deployment, or secret value was changed or read for this exercise.

**Decision-ready finding:** The VM and session-event checks are observable, but this exercise does **not** establish a private-repository deny boundary, demonstrate injection of a configured secret, or establish an enforced human-approval gate. In particular, GitHub reports `main` unprotected and the visible `Protect Main` ruleset disabled. A draft PR is a review workflow, not itself a technical prohibition on bypassing review.

| Question | What was observed | What it does **not** prove |
| --- | --- | --- |
| VM, network and filesystem | Parent VM: hostname `devin-box`; Ubuntu 22.04.5 LTS; `lo` (`127.0.0.1/8`, `::1/128`), `ens5` (`172.16.255.2/30`, link-local IPv6), and a DOWN `docker0` (`172.17.0.1/16`). `/home/ubuntu` is on `/dev/vda1` (`ext4`). A non-secret marker under the parent's `/home/ubuntu/Documents` was **missing** when checked on the second session's VM. [Parent screenshot](evidence/agent-vm-parent.png); [second-session result](https://partner-workshops.devinenterprise.com/sessions/c7c1c5776d3e4b50b14534999b5e41e7). | Identical hostname strings do not imply the same VM. The absent marker is a point-in-time test of two sessions, not a proof that all paths, integrations, or future sessions cannot share data. Interface inventory is not an egress policy or a network-isolation test. |
| Ephemerality | [Devin's environment documentation](https://docs.devin.ai/onboard-devin/environment#how-sessions-work) says each session starts from a fresh copy of a prebuilt snapshot and changes do not persist back to it. | The running VM cannot prove its own teardown. Snapshots and explicitly configured persistence are exceptions to an absolute claim that *nothing* can survive a session. Verify lifecycle/retention settings with the platform owner. |
| Repository reachability | `git ls-remote origin HEAD` succeeded against `Cognition-Partner-Workshops/otterworks` at `19392116c2197d713811213778a7a1d75eb90cc0`; GitHub API reports `private=false`, default branch `main`. [Reachability screenshot](evidence/agent-repo-reachable.png). | This is a **public** repository: a successful read alone cannot prove the identity was granted private repository access. No other repository was cloned, read, or modified. An existing, authorized-to-probe private repository outside the grant set was not named; therefore **no denied-repository error was captured**. Do not treat a nonexistent repository's 404 as proof of denial. |
| Secret handling | The session's secrets inventory returned **no configured secrets**. A name-only check of the terminal environment for `_TOKEN`, `_KEY`, `_SECRET`, `_PASSWORD`, or `_CREDENTIAL` returned `[]` (count `0`); no values were printed. [Names-only screenshot](evidence/agent-secret-names.png). [Devin's environment documentation](https://docs.devin.ai/onboard-devin/environment#environment-variables-and-secrets) states that configured secrets are injected as environment variables during builds and sessions. | With zero configured secrets there are no secret variable names to show, and this run cannot demonstrate actual injection. The pattern-based check does not enumerate every possible variable name. “Never printed” describes this exercise's handling, **not** a platform guarantee that future commands or third-party tools cannot disclose secrets. |
| Timeline visibility | The `devin_session_events` API returned timestamped message and shell events, with event IDs and start/update/completion types. [Event-metadata screenshot](evidence/agent-session-events.png) is a names-only, derived excerpt; inspect the [authenticated session timeline](https://partner-workshops.devinenterprise.com/sessions/332224df477f44f6865622e222f146eb) and [second session](https://partner-workshops.devinenterprise.com/sessions/c7c1c5776d3e4b50b14534999b5e41e7) for the source history. | This establishes event visibility for the sampled actions, not completeness, tamper resistance, access policy, or retention of every possible external action. A fresh browser without a login could not open the authenticated session page; the event API was used instead. |
| Code-change path / approval | Work is confined to a non-default branch and a draft PR; **no merge is requested or performed**. GitHub branch metadata reports `main` as `protected=false`; the `Protect Main` ruleset is `disabled`. The branch-protection-detail API returned `403 Resource not accessible by integration`. [Guardrail screenshot](evidence/agent-pr-guardrails.png). [GitHub integration guidance](https://docs.devin.ai/integrations/gh#security-considerations) recommends branch protection and notes that Devin uses organization-granted integration permissions. | An agent using a PR voluntarily is not evidence that a person *must* approve all changes. This repository currently has no verified enforced PR-review gate on `main`; the 403 prevents inspecting any additional protection detail with this identity. Repo owners should enforce required PR reviews, required checks, no direct pushes/bypass for the agent identity, and test rejection of an unapproved merge/direct write with an authorized administrator. |

## Exact read-only probes

Run from the `otterworks` checkout. These commands do not print credentials or enumerate another repository's contents:

```bash
hostname
grep -E '^(PRETTY_NAME|VERSION_ID)=' /etc/os-release
ip -brief address
findmnt -o TARGET,SOURCE,FSTYPE -T /home/ubuntu
git ls-remote origin HEAD
gh api repos/Cognition-Partner-Workshops/otterworks --jq '{private,default_branch}'
gh api repos/Cognition-Partner-Workshops/otterworks/branches/main --jq '{name,protected}'
gh api repos/Cognition-Partner-Workshops/otterworks/rulesets --jq '[.[] | {name,enforcement}]'
gh api repos/Cognition-Partner-Workshops/otterworks/branches/main/protection --jq '.required_pull_request_reviews'
```

The final command exited `1` with `gh: Resource not accessible by integration (HTTP 403)`. This is a denied **operation within this repository**, not evidence that a different repository is inaccessible. The other listed probes completed successfully.

For the screenshot's name-only environment check:

```python
import os

names = sorted(
    name for name in os.environ
    if any(part in name for part in (
        "_TOKEN", "_KEY", "_SECRET", "_PASSWORD", "_CREDENTIAL"
    ))
)
print("Secret-style environment variable names only:", names)
print("Count:", len(names))
```

**Follow-up observation, 2026-11-05 12:49 UTC:** On continuation of this same session, the parent marker was still present, `main` still reported `protected=false`, and `Protect Main` still reported `disabled`. Session continuation is therefore **not** a teardown demonstration; do not equate pausing or resuming a session with destruction of its filesystem. No branch rules, credentials, or security profiles were changed to manufacture a successful result.

## Reproduce without disclosing credentials

1. In two separate sessions restricted to this repository, create a non-secret marker in the first session's home directory and check for its absence in the second; compare the session links, not just the shared hostname string. Confirm the expected fresh-snapshot and cleanup behavior with the platform operator.
2. Read this repository's remote HEAD and metadata. For a *meaningful* denial test, obtain the name of a known-existing private repository explicitly authorized for a read-only permission probe, then capture the exact authentication/authorization error. Do not clone it or confuse “not found” with “not permitted.”
3. In the Devin secrets settings, check names/scopes without opening values; a future controlled test may inject a canary and print **only** its variable name and presence boolean, never its value. Inspect the authenticated session timeline and the corresponding SCM audit events.
4. Have a repository administrator enable and verify enforced branch/PR protection, including agent bypass policy; attempt a controlled unapproved merge/direct write **only with explicit authorization**. A draft PR alone cannot substitute for this control.

## Independent administrator checks

These links are inspection entry points, not evidence that any particular configuration is enabled:

- [Repository permission scope](https://partner-workshops.devinenterprise.com/settings/connections/github#github-repo-permissions): verify the integration's granted repositories and identify a known-existing, out-of-scope private control repository before authorizing its probe.
- [Session security profiles](https://partner-workshops.devinenterprise.com/settings/devin#security-profiles): verify the effective mandatory profile, git access level, and network policy. A private IP address alone is not evidence of an egress allowlist.
- [Organization secret names/scopes](https://partner-workshops.devinenterprise.com/settings/secrets?tab=org) and [personal secret names/scopes](https://partner-workshops.devinenterprise.com/settings/secrets?tab=personal): inspect names without opening values. Do not supply a production credential merely to complete this demonstration.
- [GitHub repository rules](https://github.com/Cognition-Partner-Workshops/otterworks/settings/rules): verify enforced PR approvals and agent bypass restrictions using an administrator's own identity. This session did not change those settings.

## Evidence index

| Evidence | Inspect directly |
| --- | --- |
| Parent session | [Commands, outputs and messages](https://partner-workshops.devinenterprise.com/sessions/332224df477f44f6865622e222f146eb) |
| Second-session isolation check | [Read-only result](https://partner-workshops.devinenterprise.com/sessions/c7c1c5776d3e4b50b14534999b5e41e7); tags: `cio-cto`, `FSX_20261105`, `fs-26`, `fs-showcase` |
| Documentation-only draft PR | [PR #2560 into main](https://github.com/Cognition-Partner-Workshops/otterworks/pull/2560); [live CI checks](https://github.com/Cognition-Partner-Workshops/otterworks/pull/2560/checks) |
| Automated review | [Live Devin Review state and findings](https://partner-workshops.devinenterprise.com/review/cognition-partner-workshops/otterworks/pull/2560); automated review does not substitute for a human approval gate |
| Five full-desktop screenshots | [VM](evidence/agent-vm-parent.png), [repository](evidence/agent-repo-reachable.png), [environment names](evidence/agent-secret-names.png), [derived event index](evidence/agent-session-events.png), [approval controls](evidence/agent-pr-guardrails.png) |

**What a CISO can verify for themselves:** Open the two session links and the draft PR, inspect the screenshots and event history, then independently verify repository grant scope, secret configuration, and enforced branch rules in the Git provider's admin and audit views.
