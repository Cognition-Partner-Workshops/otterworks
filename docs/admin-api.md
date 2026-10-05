# Admin API

The Admin API is served by `admin-service` under the `/api/v1/admin` prefix via the
API gateway. Every request must carry a JWT bearer token, enforced by
`app/middleware/jwt_authenticator.rb` (`Authorization: Bearer <token>`); requests
without a valid token are rejected before reaching the controllers.

## GET /api/v1/admin/metrics/summary

Returns a point-in-time metrics snapshot aggregated by `MetricsAggregator`
(`app/services/metrics_aggregator.rb`).

### Response `200 OK`

```json
{
  "timestamp": "2026-10-05T12:00:00Z",
  "users": {
    "total": 42,
    "active": 38,
    "suspended": 3,
    "by_role": { "super_admin": 2, "admin": 5, "editor": 10, "viewer": 25 },
    "recent_signups": 7,
    "signed_in_today": 12
  },
  "storage": {
    "total_allocated_bytes": 107374182400,
    "total_used_bytes": 53687091200,
    "average_usage_percent": 48.5,
    "users_over_quota": 2,
    "by_tier": { "free": 30, "pro": 12 }
  },
  "features": {
    "total": 15,
    "enabled": 9,
    "disabled": 6
  },
  "announcements": {
    "total": 4,
    "active": 1,
    "by_severity": { "info": 2, "warning": 1, "critical": 1 }
  },
  "audit": {
    "total_events": 12045,
    "events_today": 87,
    "events_this_week": 612,
    "top_actions": { "user.updated": 120, "document.created": 98 }
  }
}
```

| Field | Description |
| --- | --- |
| `timestamp` | ISO-8601 time the snapshot was generated. |
| `users.total` | Total admin users. |
| `users.active` | Users with status `active`. |
| `users.suspended` | Users with status `suspended`. |
| `users.by_role` | User counts grouped by role. |
| `users.recent_signups` | Users created in the last 30 days. |
| `users.signed_in_today` | **New.** Count of admin users whose `last_login_at` is at or after 00:00 UTC on the current day. |
| `storage.total_allocated_bytes` | Sum of all storage quota allocations. |
| `storage.total_used_bytes` | Sum of all storage used. |
| `storage.average_usage_percent` | Mean `used_bytes / quota_bytes * 100` across quotas. |
| `storage.users_over_quota` | Quotas where used bytes exceed the quota. |
| `storage.by_tier` | Quota counts grouped by tier. |
| `features.total` / `enabled` / `disabled` | Feature-flag counts. |
| `announcements.total` / `active` / `by_severity` | Announcement counts. |
| `audit.total_events` | All audit-log events. |
| `audit.events_today` | Audit events since 00:00 UTC today. |
| `audit.events_this_week` | Audit events in the last 7 days. |
| `audit.top_actions` | Top 5 audit actions over the last 7 days. |

## GET /api/v1/admin/users

Returns a paginated list of admin users, serialized by `AdminUserSerializer`.

### Query parameters

| Param | Default | Description |
| --- | --- | --- |
| `q` | — | Case-insensitive substring match on `email` or `display_name`. |
| `role` | — | Filter by role (`super_admin`, `admin`, `editor`, `viewer`). |
| `status` | — | Filter by status (`active`, `suspended`, `deleted`). |
| `page` | `1` | 1-based page number (clamped to ≥ 1). |
| `per_page` | `20` | Page size (clamped to 1–100). |

Pagination defaults come from `ApplicationController#paginate`, which also sets
`X-Total-Count`, `X-Page`, and `X-Per-Page` response headers.

### Response `200 OK`

```json
{
  "users": [
    {
      "id": "…",
      "email": "admin@otterworks.com",
      "display_name": "Admin",
      "role": "admin",
      "status": "active",
      "avatar_url": null,
      "metadata": {},
      "last_login_at": "2026-10-05T09:30:00Z",
      "suspended_at": null,
      "suspended_reason": null,
      "created_at": "2026-01-15T00:00:00Z",
      "updated_at": "2026-10-05T09:30:00Z",
      "storage_quota": {
        "id": "…",
        "user_id": "…",
        "quota_bytes": 5368709120,
        "used_bytes": 1073741824,
        "tier": "pro",
        "usage_percentage": 20.0,
        "over_quota": false,
        "remaining_bytes": 4294967296,
        "created_at": "…",
        "updated_at": "…"
      }
    }
  ],
  "total": 42,
  "page": 1,
  "per_page": 20
}
```

`last_login_at` is the ISO-8601 timestamp of the user's most recent sign-in, or
`null` if they have never signed in. It is displayed in the dashboard users
table as the "Last sign-in" column (rendered as "Never" when `null`).

## Known gap

Nothing currently writes `admin_users.last_login_at`. auth-service records
sign-ins in its own `users.last_login_at` column (set in `AuthService#login`)
and does not sync them to admin-service, so `users.signed_in_today` and
`last_login_at` remain `0`/`null` until that sync exists.

## Changelog

- `users.signed_in_today` added to metrics summary; the dashboard "Signed in
  today" tile and users-table "Last sign-in" column consume it/`last_login_at`.
