# Signed parity exception: dw.usp_refresh_policy_contact

- Signed by: Insurance data owner
- Date: 2026-10-21
- Scope: `dw.policy_contact.contact_label` for 266 of 2000 policies (key `policy_number`): rows where `alt_phone_label` is NULL or `''` and `LEN(alt_phone) > 10`.
- Evidence: `run-1.md` / `run-1.json` (L1 green 2000 vs 2000; L2 drift in `contact_label` only; L3 86.7%, 1734/2000; every one of the 266 differing keys has legacy `contact_label = LEFT(alt_phone, 10)`).

## Question

When a policy has no alternate-phone label, the legacy contact screen shows the alternate phone number cut to its first 10 characters (for example `+1 (555) 3` instead of `+1 (555) 309-2384`). This affects 266 of 2,000 policies. Should Snowflake show the full alternate phone number, or is the 10-character cut intended?

## Answer (verbatim)

> Snowflake should show the full alternate phone number. The 10-character cut on the legacy contact screen was never intended; it's a defect, and the call centre has worked around it for years. Please record this as a signed parity exception for the 266 policies, from the Insurance data owner, 2026-10-21, and keep the COALESCE version. Don't add LEFT(..., 10).

## Outcome

- The conversion keeps `COALESCE(NULLIF(alt_phone_label, ''), NULLIF(alt_phone, ''))` and returns the full number (rule R70). No `LEFT(..., 10)`.
- The only accepted difference from legacy is those 266 `contact_label` values. Every other column and row matches.
