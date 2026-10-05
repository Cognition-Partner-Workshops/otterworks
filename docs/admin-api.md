# Admin API

Admin endpoints are exposed through the API gateway under `/api/v1/admin` and
require an admin JWT in the `Authorization: Bearer <token>` header.

## Storage usage

`GET /api/v1/admin/storage/usage` returns the actual stored-file usage for all
admin users. The byte totals are calculated from file-service metadata, rather
than storage quota values. Trashed files are included because they continue to
occupy storage.

Example response:

```json
{
  "total_bytes": 1536,
  "file_count": 2,
  "generated_at": "2026-07-20T14:30:00Z",
  "users": [
    {
      "user_id": "8eec74b8-1f6f-4d2a-b826-c0ad3da1aa72",
      "file_count": 2,
      "total_bytes": 1536
    },
    {
      "user_id": "7e62dc4a-7d9a-4f79-9a43-9c2e216d0a9e",
      "file_count": 0,
      "total_bytes": 0
    }
  ]
}
```

If file-service cannot provide usage data, admin-service returns
`502 Bad Gateway`:

```json
{ "error": "File service unavailable" }
```

### Internal file-service contract

Admin-service requests usage from file-service at
`POST /internal/usage` with a JSON body containing `owner_ids`, an array of
UUIDs. The endpoint returns `file_count`, `total_bytes`, and one `owners` entry
per distinct owner, including zero-valued entries for owners without files.
Requests are limited to 100 owner IDs. Invalid UUIDs or requests exceeding that
limit return `400 Bad Request`. File-service queries the `owner-index` metadata
index and includes trashed files in its totals.
