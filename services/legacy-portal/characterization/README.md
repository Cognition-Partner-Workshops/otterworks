# legacy-portal characterization suite

Live-HTTP tests that pin the portal's observable behavior (status codes, media types, JSON bodies
and key order, error shapes, no-auth, persistence order). They were recorded against the Java 11 /
Spring Boot 2.7.18 build and run unchanged against later builds. Standard library only.

The suite is ordered and stateful, so start each run on a fresh database.

```bash
# H2 (default profile): restart the process before each run
SKIP_BUILD=1 SERVER_PORT=18095 ./scripts/run-onprem.sh &
BASE_URL=http://localhost:18095 CHAR_BACKEND=h2 python3 characterization/test_characterization.py

# PostgreSQL (on-prem compose profile): `down -v` before each run
docker compose -f docker-compose.onprem.yml down -v && docker compose -f docker-compose.onprem.yml up -d --build --wait
BASE_URL=http://localhost:8095 CHAR_BACKEND=postgres python3 characterization/test_characterization.py
```

The last line of the output is the summary, e.g. `Tests run: 50, Failures: 0, Errors: 0, Skipped: 0`.
`CHAR_BACKEND` only selects the expected row order of an unsorted `findAll()` after an UPDATE,
which depends on the database, not on the runtime.
