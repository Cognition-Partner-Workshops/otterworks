# Legacy portal run of show

You present from Partner Demo - ViewOnly, signed in as the AWS persona. The operator commands run on a machine with a checkout of `Cognition-Partner-Workshops/otterworks` and AWS admin credentials in the environment. The prompts are in `prompts.md` in this folder, and the harness is described in `README.md`.

## Signing in as the AWS persona

1. Open https://fieldkit.devin.ai and sign in with your magic link.
2. Open https://partner-workshops.devinenterprise.com/auth/login?redirect=/&reauth=true and choose "Log in with SSO".
3. Pick `Devin-Demo-AWS` when the Field Kit page asks for a persona.
4. Land on the ViewOnly sessions list. If the page shows an org picker, choose Partner Demo - ViewOnly.

The demo record names an architect, a modernization engineer and a cloud engineer. In this run of show the AWS persona plays all three, so nobody has to switch accounts during the call.

## The day before

1. Pick the run token, for example `lp-20261005-rh` for a rehearsal or `lp-20261006-lv` for the live call. A rehearsal and a live run can exist side by side because every name and the Terraform state key carry the token.
2. Run `make lp-up RUN=<token>`. In the rehearsal on 2026-10-05 it took the time recorded in `rehearsal.md`, most of it on the Aurora writer.
3. Run `make lp-status RUN=<token>` and keep the API URL. Every route answers 501 until the children deploy their handlers.
4. Start the parent session from `prompts.md` as the AWS persona, in Fusion mode, on repository `Cognition-Partner-Workshops/otterworks`. Let it fan out the three children and let every child post its first replay and pause.
5. Let the Announcements and User Preferences children take their fix instruction and reach a full replay with every case identical. Leave the Feedback child paused at its first replay for the call.

## Tabs in order

1. The parent session in ViewOnly.
2. The Feedback child, paused at its first replay.
3. The integration pull request with Devin Review, once it exists.
4. The AWS console on Lambda, filtered by tag `run_token=<token>`.
5. `services/legacy-portal/README.md` on `main`.

## Act 1, the monolith

Open `services/legacy-portal/README.md` on `main` and point at the three-context table.

Say: "Three contexts, three schemas, one JVM, and nobody here has run it since the team that wrote it left. We have the code and the responses someone recorded before the last instance was switched off."

## Act 2, the fan-out

Open the parent session and its three children.

Say: "The architect asked for one target shape and three contexts. Devin split the work the way the schemas already split it: one child per context, one Lambda function each behind one HTTP API, the data on Aurora Serverless v2, all of it Terraform under one run token. Nothing on main changed."

## Act 3, the first replay

Open the Feedback child at its first replay and read the table and the first divergence it printed. The replay compares the status code, the media type and the body of each case with the recorded Java response.

Say: "The function connects and answers, so a reviewer skimming the diff might merge it. The replay against the recorded Java responses stops at the first case that disagrees."

## Act 4, the decision

As the architect, reply in the Feedback child with the steer line from `prompts.md`:

```text
Fix the Feedback adapter until every case in the recorded corpus passes against the deployed function, do not change requests.json or java-reference.json, commit the replay report, and open the pull request.
```

While the child works, open a terminal on the operator machine and show the checksum file:

```bash
cd services/legacy-portal/parity && sha256sum -c SHA256SUMS
```

Say: "We treat the recording as the contract. Devin changes its own code until the recording agrees, and the replay refuses to run if anyone edits the recording."

When the child posts its full replay, run it again yourself against the same URL:

```bash
make lp-reset RUN=<token> CTX=feedback
make lp-replay RUN=<token> CTX=feedback STAGE=full
```

## Act 5, the console

Show Lambda, API Gateway and the Aurora cluster filtered by tag `run_token=<token>`, then the CloudTrail rows the session posted under role session `devin-<session id>`, then `main` in the README tab.

Say: "Three functions that cost nothing while idle, a database that pauses at its floor, and the before state exactly where it was. Every change Devin made in the account shows under its own session name."

## Close

Say: "The source system never ran during any of this. If your customer has a monolith as code and a recording of how it answered, this is the proof they can take to their change board."

## Fallback

If the Feedback child does not resume, open the completed Feedback session from the rehearsal and its committed replay report. If the API answers 5xx on every route, run `make lp-status RUN=<token>`; a function still showing runtime `python3.12` has not been deployed by its child yet.

## After the call

Run these on the operator machine, in this order, and keep both transcripts.

```bash
make lp-down RUN=<token>
make lp-verify-clean RUN=<token>
```

`lp-verify-clean` ends with `CLEAN` when the Resource Groups Tagging API lists nothing tagged with the token in any region and the run's IAM role, policy, cluster, API, functions, secret and log groups are gone.
