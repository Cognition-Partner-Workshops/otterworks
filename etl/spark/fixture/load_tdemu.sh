#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
python3 - "${LANDING_DIR:-etl/spark/.data/${NS:-sfx-d1110-before}/landing}" <<'PY' | docker compose -f docker-compose.spark.yml -p "sfx-d1110-spark-${NS:-sfx-d1110-before}" exec -T sfx-tdemu psql -v ON_ERROR_STOP=1 -U etl_batch -d sfx_teradata
import sys
from pathlib import Path
sys.path.insert(0, "etl/spark/jobs/py")
from common.schemas import SCHEMAS, TABLES
landing = Path(sys.argv[1])
print("BEGIN;")
for area, tables in TABLES.items():
    schema = "sfx_" + area
    print(f"CREATE SCHEMA IF NOT EXISTS {schema};")
    for table in tables:
        columns = ", ".join(f"{name} {kind}" for name, kind in SCHEMAS[table])
        print(f"DROP TABLE IF EXISTS {schema}.{table};")
        print(f"CREATE TABLE {schema}.{table} ({columns});")
        files = sorted((landing / area / table).glob("*.psv"))
        if not files:
            raise SystemExit(f"No landing files for {area}/{table}")
        for file in files:
            path = f"/opt/landing/{area}/{table}/{file.name}"
            print(f"COPY {schema}.{table} FROM '{path}' WITH (FORMAT csv, HEADER true, DELIMITER '|', NULL '');")
print("COMMIT;")
PY
