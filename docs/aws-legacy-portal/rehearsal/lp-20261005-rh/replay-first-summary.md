# legacy-portal replay against the recorded Java responses

Target: `https://iukn6912ki.execute-api.us-east-1.amazonaws.com/`

Java: `java-reference.json` (recorded capture)

Stage: `first`

Started (UTC): 2026-10-05T08:09:19Z

| Context | Cases in corpus | Cases run | Identical | Different | First divergence | Result |
|---|---|---|---|---|---|---|
| common | 10 | 1 | 0 | 1 | common-01 | stopped at common-01 |
| announcements | 36 | 1 | 0 | 1 | ann-01 | stopped at ann-01 |
| preferences | 20 | 1 | 0 | 1 | pref-01 | stopped at pref-01 |
| feedback | 29 | 1 | 0 | 1 | fb-01 | stopped at fb-01 |

0/4 replayed cases identical.

## common-01 (common)

`GET /health`: status 200 != 501; body differs

Java (recorded):
```
200 application/json
{"status": "UP", "service": "legacy-portal", "banner": "OtterWorks Portal (on-prem) - contact portal-support@otterworks.example"}
```
Target:
```
501 application/json
{"error": "not implemented", "context": "announcements", "path": "/health"}
```

## ann-01 (announcements)

`GET /api/announcements`: status 200 != 501; body differs

Java (recorded):
```
200 application/json
[]
```
Target:
```
501 application/json
{"error": "not implemented", "context": "announcements", "path": "/api/announcements"}
```

## pref-01 (preferences)

`GET /api/preferences/newuser`: status 200 != 501; body differs

Java (recorded):
```
200 application/json
{"userId": "newuser", "theme": "light", "locale": "en-US", "emailNotifications": true}
```
Target:
```
501 application/json
{"error": "not implemented", "context": "preferences", "path": "/api/preferences/newuser"}
```

## fb-01 (feedback)

`GET /api/feedback/average-rating`: status 200 != 501; body differs

Java (recorded):
```
200 application/json
{"averageRating": 0.0}
```
Target:
```
501 application/json
{"error": "not implemented", "context": "feedback", "path": "/api/feedback/average-rating"}
```
