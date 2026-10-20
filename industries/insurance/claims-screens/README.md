# Claims screens

Three screens in the client-app's pine-and-brass skin (`frontend/client-app`: its Tailwind theme, `globals.css` and mark,
imported, not copied), over a small JSON API that can stand on either side of the hub move:

| Screen | Route | Shows |
|---|---|---|
| FNOL intake | `/` | submit a corpus FNOL (`corpus/inputs/fnol`), get the claim number, triage outcome, reasons and the FnolIntake instance state |
| Claim status | `/claims/:claim` | claim, policy, outcome, reasons, adjuster |
| Payment confirmation | `/payments/:id` | instruction, payee, lines (instructed and remitted), vendor reference, ledger net, file net, file status |

`api/claims_api.py --source golden` reads only `biztalk-claims-intake/corpus/golden`. `--source camel` reads only what a
running `claims-hub-camel` wrote: the FnolIntake tracking drop, the `claim` and `ledger.claim_payment_entry` tables,
the vendor's SFTP inbox and the SMTP sink. Nothing is filled in from the other side; a value the source does not have
is shown as missing, with the reason.

## Access

Every API request needs `Authorization: Bearer <token>`; the API will not start unless `CLAIMS_SCREENS_READER_TOKEN`
and/or `CLAIMS_SCREENS_ADJUSTER_TOKEN` is set (16 characters at least, the two different). A reader token gets the
claimant name and a claimant payee's name and account masked the way the `claims_api` PostgreSQL views mask them
(`compliance.mask_name`, `compliance.mask_account`; vendor and salvage payees stay readable). An adjuster token gets
them in clear. The dev server's proxy sends `CLAIMS_API_TOKEN` as the bearer token.

## Run

```bash
export CLAIMS_SCREENS_READER_TOKEN=$(openssl rand -hex 16) CLAIMS_SCREENS_ADJUSTER_TOKEN=$(openssl rand -hex 16)
export CLAIMS_API_TOKEN=$CLAIMS_SCREENS_READER_TOKEN   # or the adjuster token to see claimant PII in clear

# before: the BizTalk goldens
python3 api/claims_api.py --source golden --port 8095 &
(cd web && npm install && CLAIMS_API=http://127.0.0.1:8095 PORT=5181 npm run dev)

# after: claims-hub-camel over the same corpus messages (Java 21, Docker)
pip install -r api/requirements.txt
hub/hub.sh up                      # PostgreSQL 16, MailHog, vendor SFTP, seeded; the hub jar on :8092
hub/hub.sh replay CLM-2026-100405 CLM-2026-100400 CLM-2026-100403   # all assignments and payments, the other 13 FNOLs
python3 api/claims_api.py --source camel --port 8096 &
(cd web && CLAIMS_API=http://127.0.0.1:8096 PORT=5182 npm run dev)  # submit the three FNOLs from the intake screen
hub/parity.py                      # one row per corpus unit, Camel output against its golden
hub/hub.sh down                    # stops the hub and removes every container
```

The hub runs with `claimshub.local-inbox.enabled=true`: FNOLs and assignment requests are picked up one per file from
`hub/run/inbox` (in place of the SFTP batch and WCF-SQL polling receive locations) and FnolIntake's completed and
suspended reports go to `direct:tracking.fnol`, which writes the instance record the API reads. The payment receive
location is the hub's own FILE inbox. The vendor's 22:00–05:30 window is switched off for the replay
(`VENDOR_WINDOW=true hub/hub.sh up` keeps it).

`cd web && npm test` runs the screen tests; `python3 -m unittest discover -s api` runs the API auth and masking tests.
