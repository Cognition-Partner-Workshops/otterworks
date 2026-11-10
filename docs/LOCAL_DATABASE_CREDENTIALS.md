# Local database credentials

Before first use, run `python3 scripts/local-env.py` in the repository. It creates
a gitignored root `.env` with independent random `DB_PASSWORD` and
`BILLING_SVC_DB_PASSWORD` values, mode 0600, and refuses to overwrite an existing
file. If `.env` already exists, preserve its other settings and provision these
two variables yourself using random URL-safe values (the generated hexadecimal
values are safe to interpolate in connection URLs). Never commit the file.

Compose automatically reads this file, so `make up`, `make infra-up` and
`make procs-up NS=dev` use the same credentials on both sides of each connection.
For host-side seed, validation and procs harness commands, first export its values:

```sh
set -a
source .env
set +a
make seed
```

Seed helpers no longer embed a password fallback. They accept `DB_PASSWORD`, or
normal libpq authentication such as a protected `.pgpass` file. The helpers in
`testdata/generated/seed/helpers.py` are themselves generation code, not output
from a separate template.

Document-service and Alembic require `DOC_SVC_DATABASE_URL`; Compose supplies it
using `DB_PASSWORD`. Host-side invocations must supply it explicitly. Use a URL
with appropriate percent-encoding if credentials contain reserved URL characters.

Existing Postgres volumes retain their old passwords: changing `.env` does not
rotate database roles. Rotate the existing roles securely to match before
restarting services, or deliberately recreate only disposable development volumes
after backing up any data you need. Rotate all formerly committed credentials.

The admin dashboard now requires a successful gateway login. Network errors and
rejected credentials surface as errors; no offline admin session is created.
