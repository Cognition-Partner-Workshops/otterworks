# Attacker paths visible from the DAST probes (otterworks, demo-bank)

Source: the probe registry in `security/dast/harness/probes/` (`make dast-list`)
and the controls each probe attacks. Verdict column is from a local
`make dast-scan` against the demo-bank build (see "Verdicts" below); paths are
chains of those findings, not separately exploited.

## Why these three classes were chosen for detection

| Class | Probes | Why it ranks for a bank |
|---|---|---|
| Identity forgery | DAST-UNSIGNED-JWT, DAST-IDENTITY-HEADER-SPOOF, DAST-SHARE-TOKEN-FORGERY (DAST-GATEWAY-BYPASS-IDENTITY feeds it) | Acting as another customer without their credentials. Every downstream control trusts the identity the gateway forwards, so one forged identity is total account takeover. |
| Cross-customer data access | DAST-BOLA-DOCUMENTS, DAST-MASS-ASSIGNMENT-OWNER, DAST-PATH-TRAVERSAL-EXPORT (DAST-SEARCH-TENANT-LEAK is the same class) | Reading or planting objects in another customer's account: statements, KYC uploads. This is the reportable-breach class (GLBA / GDPR Art. 33). |
| Credential stuffing | DAST-CREDENTIAL-BRUTE-FORCE, DAST-RATE-LIMIT-BYPASS | The most common real-world route to retail-bank account takeover; no lockout plus a spoofable per-IP limiter means unlimited guesses from rotating addresses. |

Runner-up: injection (DAST-SQLI-ERROR-BASED, DAST-STORED-XSS-DOCUMENTS). SQLi is
critical but is already visible as 5xx / 400 bursts under the existing
`HighErrorRate` rules; the three above produce *no* error signal when they
succeed, so they were blind without new instrumentation.

## Paths

**P1 — Credential stuffing to account takeover.** Rotate `X-Forwarded-For`
(DAST-RATE-LIMIT-BYPASS) so every attempt lands in a fresh limiter bucket →
unlimited password guesses against one account (DAST-CREDENTIAL-BRUTE-FORCE) →
the login response returns more of the user record than needed
(DAST-SENSITIVE-DATA-IN-RESPONSE) → valid session as the victim.
Detected by: SecurityLoginFailureBurst, SecurityLimiterClientChurn,
SecurityRateLimitRejections.

**P2 — Forged or injected identity.** A token the gateway mis-validates
(DAST-UNSIGNED-JWT), a client-supplied `X-User-ID` honoured downstream
(DAST-IDENTITY-HEADER-SPOOF), or any backend origin reachable without the
gateway (DAST-GATEWAY-BYPASS-IDENTITY), lets an attacker *name* the victim
instead of logging in as them. Share links are a second, unauthenticated
version: a token derivable offline (DAST-SHARE-TOKEN-FORGERY) opens any
document whose id is known.
Detected by: SecurityJWTRejected, SecurityIdentityHeaderInjected,
SecurityShareTokenRejected.

**P3 — Enumerate, then read across customers.** Search results that ignore
tenancy (DAST-SEARCH-TENANT-LEAK) hand out other customers' document ids →
direct object reads by id (DAST-BOLA-DOCUMENTS) or the export archive read with
`../` (DAST-PATH-TRAVERSAL-EXPORT, which also reaches files outside any
customer's data) → exfiltration. DAST-MASS-ASSIGNMENT-OWNER is the write side:
plant a document in the victim's account, combined with stored XSS
(DAST-STORED-XSS-DOCUMENTS) to run script in the victim's session.
Detected by: SecurityCrossOwnerAccess, SecurityExportPathTraversal,
SecurityOwnerOverride.

**P4 — Edge reconnaissance and browser pivot (not detected by this change).**
Unauthenticated admin/audit/analytics routes (DAST-UNAUTHENTICATED-ADMIN,
DAST-ANONYMOUS-ROUTE-SWEEP) and `/metrics` / actuator endpoints
(DAST-EXPOSED-TELEMETRY) map users and internals without a token; verbose
errors (DAST-VERBOSE-ERRORS) and SQL errors (DAST-SQLI-ERROR-BASED) confirm the
schema. A credentialed CORS reflection (DAST-CORS-ORIGIN-REFLECTION) plus
missing browser headers (DAST-MISSING-SECURITY-HEADERS) lets a hostile page
read API responses with a logged-in customer's cookies — feeding P3 without
the attacker ever holding credentials.

## Gaps and hand-off to the fineract / internet-banking tracing

- Search-service tenancy (DAST-SEARCH-TENANT-LEAK) is in the class but is not
  instrumented here; the document-service `/search` route is.
- P4 has no detection in this change.
- Identity in otterworks is a gateway-forwarded header. If fineract or internet
  banking accept the same JWT secret or the same `X-User-ID` convention, P2
  crosses systems; that is the first thing to check in the other run's paths.

## Payment-approval paths (fineract, internet banking): what these detections would catch

Source: the payment-approval initial attacker-path write-up
(ts-java-spring-boot-internet-banking#41). **Every path below is
scanner-reported and not yet proven** — no runtime reproduction, no failing
test, scanned SHA not pinned. Severity is the scan's.

The rules in this change read metrics that only the otterworks api-gateway
and document-service emit. Neither fineract nor internet banking emits them,
so **as deployed, none of the three classes catches any of these paths**. The
"would catch" column is what happens once the same counter is added to the
named service and the rule pointed at it.

| Scanner-reported path (unproven) | Identity forgery | Cross-customer access | Credential stuffing |
|---|---|---|---|
| FIN checker approves/rejects/deletes another office's maker-checker entry (sfind-8768dfac, medium) | Miss: valid checker token | Would catch with an office-mismatch counter in `validateMakerCheckerTransaction` | Miss |
| FIN loan transaction/charge/disbursal skips office check (sfind-4e48bdf3, medium) | Miss | Would catch (same office-mismatch counter) | Miss |
| FIN recurring-deposit read/change from any office (sfind-d99c2356, medium) | Miss | Would catch | Miss |
| FIN recurring-deposit deposit/withdraw/reverse from any office (sfind-7fbdb088, medium) | Miss | Would catch | Miss |
| FIN savings charges read/waive/pay/delete from any office (sfind-6f4f7b83, medium) | Miss | Would catch | Miss |
| FIN cashier allocate/settle across offices (sfind-cbcb7cbc, medium) | Miss | Would catch | Miss |
| FIN office transactions outside hierarchy (sfind-d832eeca, low) | Miss | Would catch | Miss |
| IB gateway accepts any realm token, no role check; committed client secret (sfind-e580a5bf, critical) | Miss: the token is genuinely signed, so nothing is rejected. Needs a role-or-client-id check counter | Miss on its own; catches the follow-on cross-account calls | Miss |
| IB anonymous `..` after a public actuator prefix reaches every backend (sfind-930d44f2, critical) | Miss: no token is presented. The `..` matcher only exists for the document export route | Miss | Miss |
| IB backend host ports skip the gateway (sfind-ac7cde3a, critical) | Miss: traffic never reaches the gateway, where the counters are. Same blind spot as DAST-GATEWAY-BYPASS-IDENTITY | Catches only if the counter sits in the backend, not the gateway | Miss |
| IB transfer/utility payment debits any named account (sfind-ee4ab8ab, sfind-640f8ec8, sfind-87d6d204, critical) | Miss | Would catch: source account owner ≠ caller is the same signal as `cross_owner_object` | Miss |
| IB negative or sub-cent amounts (sfind-821ac1aa, critical) | Miss | Miss: the attacker uses their own `fromAccount` | Miss: business-logic flaw, needs an amount-sign/scale counter |
| IB any user approves any pending registration (sfind-a9add981, high) | Miss | Would catch: record owner ≠ caller | Miss |
| IB utility-payment and transfer list endpoints return every customer's rows (sfind-364ecc21, sfind-cb04485e, critical) | Miss | Would catch: rows with owner ≠ caller, like the `/search` hook here | Miss |

Takeaways:
- Cross-customer access is the class that carries over. The pattern behind
  13 of the 17 paths is the caller reading or moving another owner's or office's
  record. A counter at that check, paged on any increase, is the one
  detection to add to both repositories.
- Credential stuffing catches none of them. These paths all start from a valid
  login or no login at all.
- Identity forgery as built here catches none of them. The internet-banking
  problems are *valid* tokens with no role check, and routes around the
  gateway. A forged-token counter cannot see either. A gateway counter for
  "authenticated but role or client not allowed", plus detection inside the
  backends, would close the gap.
- No class covers negative amounts.

## Internet-banking fix signals (ts-java-spring-boot-internet-banking #53)

The internet-banking fix flagged five signals. Each one has a gateway
detection and a replay class (`make detect-replay CLASS=ib-*`), with before
and after evidence in `security/detection/evidence/`. Otterworks has no
payment, account or bank-user services: those routes return 404 here. So
these alerts are **edge tripwires**. The checks that decide whether an attack
worked belong in the internet-banking services. Every replay records the
exploitation verdict as `inconclusive`.

| Signal | Detection (`api_gateway_security_events_total`) | Alert | What otterworks can see |
|---|---|---|---|
| Anonymous call to `/transaction/fund-transfer`, `/utility-payment` | `payment_route_call{reason=anonymous}` | `SecurityPaymentRouteAnonymous` | **Visible.** The gateway sees the path and that no valid token was sent. |
| **Non-owner** call to the same routes | none | none | **Not visible.** The gateway has no account-ownership data, and the routes don't exist here. Authenticated calls are counted (`reason=authenticated`) but do not alert. This check has to live in internet banking's fund-transfer and utility-payment services. |
| Amount ≤ 0 or more than 2 decimal places | `payment_amount_invalid{reason=non_positive\|precision}`, top-level JSON `amount` on payment routes only | `SecurityPaymentAmountInvalid` | **Visible at the edge.** The body is inspected even though the route 404s. A body nested differently or not sent as JSON is not seen. Billing (6-decimal `overage_rate`) and statement entries (negative amounts) are deliberately excluded. |
| `X-Auth-Id` that doesn't match the JWT `sub` | `auth_id_mismatch{reason=mismatch\|unauthenticated}` | `SecurityAuthIdMismatch` | **Visible.** Checked on every route. No otterworks service reads `X-Auth-Id`, so here it is attempted spoofing only. |
| Non-admin calling `/bank-users` | `admin_route_non_admin{reason=bank_users\|admin_api}`; roles[] lacks `ADMIN` | `SecurityAdminRouteNonAdmin` | **Visible.** Also covers the otterworks equivalent, `/api/v1/admin/*`. |
| Repeated failed logins | `api_gateway_auth_login_total{outcome=failure}` (existing) | `SecurityLoginFailureBurst` (existing) | **Visible** for otterworks logins. Failed logins against internet banking's Keycloak never pass through this gateway. |
