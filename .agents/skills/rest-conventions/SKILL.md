---
name: rest-conventions
description: OtterWorks REST API conventions (resource names, versioning, error shape, pagination) and how legacy-billing moves its server-rendered pages and RPC-style JSON routes to /api/v1/billing behind the api-gateway while keeping the old routes as thin adapters with contract tests. Use when adding or changing any /api/v1 route, or when migrating a legacy-billing module (plans, rating, invoicing, dunning).
---

# REST conventions

The contract for billing is `services/legacy-billing/openapi/billing-v1.yaml`.
It is the source of truth; if this file and the contract disagree, fix one of
them in the same PR.

## Base path and gateway

- Every public route is `/api/v1/<service-area>/...`. Billing is
  `/api/v1/billing/...`.
- The api-gateway (`services/api-gateway/internal/config/config.go`,
  `ServiceRoutes`) maps a prefix to a backend and forwards the **full path
  unchanged**; the backend serves `/api/v1/billing/...` itself.
- Gateway routes sit behind JWT auth unless listed as public in
  `internal/middleware/jwt.go`. Billing is not public.

## Versioning

- The major version is in the path (`/v1`). There are no version headers or
  query parameters.
- Inside a version only additive changes are allowed: new routes, new optional
  request fields, new response fields. Clients must ignore unknown fields.
- Renaming or removing a field, changing a type or status code, or making an
  optional input required is breaking and needs `/v2`, with `/v1` kept
  until its callers move.
- Legacy (unversioned) routes are deprecated, not removed. They keep their
  exact status codes and bodies and add two response headers:
  `Deprecation: true` and `Link: <{v1 path}>; rel="successor-version"`.

## Resource names

- Plural, lower-case, kebab-case nouns: `/plans`, `/invoices`,
  `/rating-periods`, `/overdue-invoices`.
- Hierarchy only for real ownership: `/tenants/{tenant_id}/subscriptions`.
  At most two levels of nesting.
- No verbs in paths. An RPC action becomes a resource that the action creates:
  "finalize rating" is `POST .../rating-periods`, "issue invoice" is
  `POST .../invoices`, "schedule dunning" is `POST /dunning-schedules`,
  "suspend overdue" is `POST /suspensions`. A computed, unsaved result is a
  singular sub-resource read with `GET` (`.../rating`, `.../invoice-preview`).
- Path parameters are `snake_case` and named after the resource
  (`{tenant_id}`, `{invoice_id}`).
- Methods: `GET` reads and never changes state; `POST` creates or runs;
  `PUT`/`PATCH`/`DELETE` as usual. Request bodies are JSON
  (`Content-Type: application/json`), never form-encoded.
- Business inputs are explicit. v1 routes do not invent default dates or
  periods; a missing required input is a `400`. (Legacy defaults such as
  `on=2026-02-28` live only in the legacy adapters.)

## Fields and types

- JSON field names are `snake_case`.
- A resource's own identifier is `id`, never `<resource>_id`
  (`plan_id` -> `id` on a plan). References to other resources keep the
  `<resource>_id` form (`tenant_id`, `plan_id` in a request body).
- Do not prefix a field with its own resource name: `status` not
  `subscription_status` on an entitlement, `number`/`type` not
  `line_no`/`line_type` on an invoice line. Fields about another resource
  keep their prefix (`tenant_status`).
- Money is a decimal **string** with the database scale (`"29.00"`), dates
  are `YYYY-MM-DD`, timestamps RFC 3339, ids are UUID strings.

## Response envelope and status codes

- Single resource: `{"data": {...}}`.
- Collection: `{"data": [...], "pagination": {...}}` (see below).
- `200` read, `201` create/run (with `Location` when the created thing is
  addressable), `204` delete with no body.

## Error shape

Every non-2xx v1 response is `application/json`:

```json
{"error": {"code": "invalid_request", "message": "period_start is required",
           "details": [{"field": "period_start", "issue": "required"}]}}
```

| Status | `code` | When |
| --- | --- | --- |
| 400 | `invalid_request` | missing/malformed input, bad UUID or date, non-JSON body |
| 401 | `unauthorized` | gateway: missing or bad JWT |
| 404 | `not_found` | unknown route or resource, empty single-resource lookup |
| 405 | `method_not_allowed` | wrong method on a known path |
| 409 | `conflict` | unique violation / action already applied |
| 422 | `unprocessable` | well-formed input the database rejects (FK or CHECK violation) |
| 500 | `internal` | anything else; `message` is generic, no stack traces or SQL |
| 429 | `rate_limited` | gateway: rate limit hit (`Retry-After` set) |
| 502 / 503 | `internal` | gateway: backend unreachable / circuit breaker open |

The gateway emits this shape itself for its own rejections on `/api/v1/billing`
(`internal/middleware/billing_errors.go`); other gateway prefixes keep their
existing bodies. `details` is optional and always a list. Clients branch on `code`, not
`message`.

## Pagination

- Every collection is paginated, even short ones.
- Query: `limit` (default 50, min 1, max 200) and `cursor` (opaque string from
  the previous page). Out-of-range `limit` or a bad cursor is `400`.
- Response: `"pagination": {"limit": 50, "next_cursor": "..."}`;
  `next_cursor` is `null` on the last page.
- Order is the order the database entrypoint returns, which is stable.

## Legacy adapters (migration pattern)

- The v1 handler is the implementation: it binds inputs, calls the
  `billing.*` entrypoint, and shapes the response. Domain logic stays in
  PL/pgSQL; the Flask layer does not reproduce it.
- The legacy route becomes a thin adapter over the v1 code path: it
  translates the legacy request (form fields, JSON body, legacy defaults)
  into the v1 call and maps the v1 result back to the legacy body and status.
- Where v1 renames a field, the adapter emits the **old name**. The
  contract test declares each rename explicitly.
- Legacy error behavior (status codes, Werkzeug HTML error pages, redirects)
  is unchanged.

## Contract tests

Located in `services/legacy-billing/tests/contract/test_<module>_contract.py`
and run with `make billing-contract` (needs Docker for Postgres).

- Each test sends the same logical request to the legacy path and the v1 path,
  each from a freshly reset, seeded database, and compares status and body.
- The comparison goes through a declared mapping only: unwrap the envelope,
  apply the module's `LEGACY_RENAMES` (for example
  `{"id": "plan_id"}  # adapter keeps the old name`), map the status
  (for example v1 `201` vs legacy `200`). Anything not declared must be equal.
- Mutating routes also compare the resulting database state.
- Error cases: assert the legacy status and body are unchanged and the v1
  response uses the error shape above.
