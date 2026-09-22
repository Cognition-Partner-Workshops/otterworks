# migration/mongo — Oracle billing estate -> MongoDB (offline mode)

Local, spec-driven load path. Nothing here reaches outside the machine:
`recon_mode: offline`, every command runs as `env -u MONGODB_ATLAS_URI ...`,
and the only Mongo write target is the local db `ow_billing_offline`.

## Layout

- `loaders/spec_loader.py` — generic spec-driven loader (root rows, embeds,
  canonicalization matching `recon/canon.py`, idempotent upsert + converge-
  delete, JSONL quarantine under `quarantine/`).
- `loaders/<unit>.py` — one thin CLI per unit (e.g. `codes.py`).
- `fixtures/seed_<unit>.py` — synthetic seed into the LOCAL Oracle fixture only.
- `tools/fault_inject.py` — mutate one target doc to prove recon catches it.
- `tests/` — pytest unit tests (no DB needed).

## Env vars (names only; see /home/ubuntu/ow-fixture.env)

- `ORACLE_FIXTURE_DSN` — JSON `{"user","password","dsn"}` for the fixture.
- `MONGO_LOCAL_URI` — e.g. `mongodb://127.0.0.1:27017`.
- `MONGODB_ATLAS_URI` — must be UNSET for every command.

## Run (unit `codes`)

```bash
source ~/ow-fixture.env   # session-local secrets, never committed
env -u MONGODB_ATLAS_URI /home/ubuntu/mmp-venv/bin/python migration/mongo/fixtures/seed_codes.py
env -u MONGODB_ATLAS_URI /home/ubuntu/mmp-venv/bin/python migration/mongo/loaders/codes.py
env -u MONGODB_ATLAS_URI /home/ubuntu/mmp-venv/bin/python migration/mongo/tools/fault_inject.py --collection codes --mode alter-field
env -u MONGODB_ATLAS_URI /home/ubuntu/mmp-venv/bin/recon run --unit codes \
  --family oracle --mapping .migration/03_mapping_spec.json \
  --tolerances .migration/02_tolerances.json \
  --canonicalization /home/ubuntu/repos/mongo-migration-plugin/skills/mongo-migration/profiles/oracle.md \
  --mode fixture --source-dsn-secret ORACLE_FIXTURE_DSN \
  --target-uri-secret MONGO_LOCAL_URI --target-db ow_billing_offline \
  --allowed-targets-file .migration/allowed_targets.json --seed 1 \
  --out .migration/recon/codes/
```
