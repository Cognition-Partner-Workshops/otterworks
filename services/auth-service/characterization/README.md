# auth-service characterization

HTTP-level characterization tests that pin the observed behavior of a running
auth-service (status codes, security headers, JSON shapes, error bodies, auth
rules), including odd behavior. They are runtime-agnostic and must run
unchanged across upgrades.

```bash
./characterization/start-local.sh [image-tag]   # postgres:15-alpine + the module's Dockerfile on :8081
python3 characterization/test_characterization.py
./characterization/stop-local.sh
```

- `AUTH_BASE_URL` (default `http://localhost:8081`) points the tests at any instance.
- `AUTH_JWT_SECRET` must match the instance's `JWT_SECRET` (default: compose dev secret).
- `USE_MAVEN_MIRROR=1 ./characterization/start-local.sh` adds `maven-mirror.init.gradle`
  to the builder stage when Maven Central rate-limits (HTTP 429).
