import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import duckdb
import oracledb
import pyarrow as pa
import pyarrow.parquet as pq

from .common import checksum, identifier, metadata, token_name


def arrow_type(column, values=()):
    kind = column.type_code
    if kind == oracledb.DB_TYPE_NUMBER:
        precision, scale = column.precision, column.scale
        if precision and scale is not None and 0 <= scale <= precision <= 38:
            return pa.decimal128(precision, scale)
        numbers = [Decimal(str(v)) for v in values if v is not None]
        scale = max((max(0, -n.as_tuple().exponent) for n in numbers), default=0)
        integral = max((max(0, n.adjusted() + 1) for n in numbers), default=1)
        precision = max(1, integral + scale)
        if precision > 38:
            raise ValueError("Numeric range exceeds a lossless DECIMAL(38) mapping")
        return pa.decimal128(precision, scale)
    if kind in (oracledb.DB_TYPE_DATE, oracledb.DB_TYPE_TIMESTAMP):
        return pa.timestamp("us")
    if kind in (oracledb.DB_TYPE_TIMESTAMP_TZ, oracledb.DB_TYPE_TIMESTAMP_LTZ):
        raise ValueError("Timezone columns require an explicit extraction mapping")
    if kind in (oracledb.DB_TYPE_VARCHAR, oracledb.DB_TYPE_NVARCHAR, oracledb.DB_TYPE_CHAR, oracledb.DB_TYPE_NCHAR):
        return pa.string()
    if kind == oracledb.DB_TYPE_RAW:
        return pa.binary()
    raise ValueError("Unsupported Oracle column type")


def extract(conn, tables, out, token, ttl_hours=24):
    meta = metadata(token, ttl_hours)
    for table in tables:
        identifier(table)
    if not tables or len(set(tables)) != len(tables):
        raise ValueError("Specify distinct source tables")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    objects = []
    with conn.cursor() as cursor:
        cursor.execute("SET TRANSACTION READ ONLY")
        for table in tables:
            # SQL identifiers cannot be bound; identifier() allowlists and quotes each part.
            # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query  # noqa: E501
            cursor.execute(f"SELECT * FROM {identifier(table)}")
            rows = cursor.fetchall()
            schema = pa.schema([pa.field(c.name, arrow_type(c, [r[i] for r in rows]))
                                for i, c in enumerate(cursor.description)])
            filename = table.replace(".", "__") + ".parquet"
            path = out / filename
            count = 0
            with pq.ParquetWriter(path, schema, compression="zstd") as writer:
                for offset in range(0, len(rows), 10000):
                    batch = rows[offset:offset + 10000]
                    arrays = [pa.array([row[i] for row in batch], type=field.type) for i, field in enumerate(schema)]
                    writer.write_table(pa.Table.from_arrays(arrays, schema=schema))
                    count += len(batch)
            objects.append({"source_table": table, "name": table.split(".")[-1], "file": filename,
                            "rows": count, "sha256": checksum(path),
                            "columns": [{"name": f.name, "type": str(f.type)} for f in schema]})
    conn.rollback()
    manifest = {"version": 1, **meta, "created_at": datetime.now(UTC).isoformat(), "objects": objects}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def validate(manifest_path):
    manifest_path = Path(manifest_path)
    manifest = json.loads(manifest_path.read_text())
    token_name(manifest["token"])
    if manifest.get("version") != 1:
        raise ValueError("Unsupported manifest version")
    names = set()
    for obj in manifest["objects"]:
        identifier(obj["name"])
        if obj["name"].upper() in names:
            raise ValueError("Duplicate target table")
        names.add(obj["name"].upper())
        path = (manifest_path.parent / obj["file"]).resolve()
        if path.parent != manifest_path.parent.resolve():
            raise ValueError("Parquet path must stay inside frozen input")
        if checksum(path) != obj["sha256"] or pq.read_metadata(path).num_rows != obj["rows"]:
            raise ValueError("Frozen input checksum or row count differs")
        fields = [{"name": f.name, "type": str(f.type)} for f in pq.read_schema(path)]
        if fields != obj["columns"]:
            raise ValueError("Frozen input schema differs")
    return manifest


def load_duckdb(manifest_path, out, token, prefix="MIGRATION"):
    name = token_name(token, prefix)
    manifest = validate(manifest_path)
    if manifest["token"] != token:
        raise ValueError("Manifest token differs")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{name}.duckdb"
    if path.exists():
        raise FileExistsError("Target already exists")
    with duckdb.connect(str(path)) as conn:
        conn.execute("BEGIN")
        try:
            for obj in manifest["objects"]:
                source = str(Path(manifest_path).parent / obj["file"])
                # Table names are validated; the file path is bound separately.
                # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query  # noqa: E501
                conn.execute(f"CREATE TABLE {identifier(obj['name'])} AS SELECT * FROM read_parquet(?)", [source])
                comment = json.dumps({"token": token, "expires_at": manifest["expires_at"]})
                escaped = comment.replace("'", "''")
                # DuckDB comments require a literal; embedded quotes are doubled.
                # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query  # noqa: E501
                conn.execute(f"COMMENT ON TABLE {identifier(obj['name'])} IS '{escaped}'")
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    return path
