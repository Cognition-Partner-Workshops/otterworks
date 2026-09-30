"""Seed-derived business-hash parity on Snowflake (live; same env and skip rule as test_snowflake.py).

Rows come from the SEED-SPEC generator exactly as the Oracle estate yields them (`seed.oracle.oracle_record`:
TIMESTAMP(9) read back with fraction digits 10-12 = 000), are converted with the manifest's Snowflake typemap,
COPY'd into STG in a fresh namespace of the scratch database, and hashed by Snowflake with the VALIDATE expression.
Every staged row must hash identically to the job's source hash except the planted MIG-04 padding rows.
"""

from __future__ import annotations

import sys
from pathlib import Path

from ldm.context import Log
from ldm.convert import convert_record
from ldm.drivers.base import StagedRow
from ldm.drivers.snowflake import SnowflakeTarget
from ldm.hashing import hash_expression, source_hash
from ldm.runner import build_context, prepare_run
from ldm.staging import DirectoryBlobStore

from .conftest import FakeSource, make_manifest_tree
from .test_snowflake import _env, cleanup, pytestmark, token  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "source"))
from seed import tables as seed_tables  # noqa: E402
from seed.generate import cohort_keys  # noqa: E402
from seed.oracle import oracle_record  # noqa: E402
from seed.spec import Sizes  # noqa: E402

SCALE = 0.002


def _seed_records(sizes: Sizes) -> dict[str, list[tuple[str, bytes]]]:
    """Table -> (failure class or '', Oracle-rendered record) for every generated and planted row."""
    s_keys, ns_keys = cohort_keys(sizes)
    planted = seed_tables.planted_docarch()
    docarch = [("", oracle_record(seed_tables.docarch_generated(sizes, g))) for g in range(sizes.docarch_generated)]
    docarch += [(cls, oracle_record(row)) for cls, row in planted]
    fileaud = [
        ("", oracle_record(seed_tables.fileaud_generated_row(sizes, m, s_keys, ns_keys)[0]))
        for m in range(sizes.fileaud_generated)
    ]
    mig05_parents = [row for cls, row in planted if cls == "MIG-05-parent"]
    fileaud += [("MIG-05", oracle_record(row)) for row in seed_tables.planted_fileaud_rows(mig05_parents)]
    retnplcy = [("", oracle_record(row)) for row in seed_tables.retnplcy_rows()]
    return {"RETNPLCY": retnplcy, "DOCARCH": docarch, "FILEAUD": fileaud}


def test_seed_rows_hash_identically_on_snowflake(tmp_path: Path, token: str, cleanup) -> None:  # noqa: F811
    manifest = make_manifest_tree(tmp_path, token, snowflake_target=True)
    ctx = build_context(
        manifest,
        f"{token}-after",
        "run-parity",
        env=_env(tmp_path),
        source=FakeSource(),
        blobs=DirectoryBlobStore(tmp_path / "blobs"),
        log=Log(),
    )
    target = ctx.target
    assert isinstance(target, SnowflakeTarget)
    cleanup.append((target, ctx.namespace))
    target.connect()
    prepare_run(ctx)

    records = _seed_records(Sizes(SCALE))
    mismatched: dict[str, dict[str, str]] = {}
    hashed: dict[str, int] = {}
    for ts in ctx.tables_in_order():
        hash_cols = ts.config.hash_columns
        rows: list[StagedRow] = []
        classes: dict[str, str] = {}
        expected: dict[str, bytes] = {}
        for cls, rec in records[ts.name]:
            conv = convert_record(rec, ts.columns)
            if not conv.ok:
                continue
            classes[conv.source_key] = cls
            expected[conv.source_key] = source_hash(conv.source_text, hash_cols, ts.columns)
            rows.append(StagedRow(ts.name, conv.source_key, 1, rec, conv.target_row()))
        rejected = {f.source_key for f in target.insert_staging(ctx.run_id, ctx.namespace, ts.name, rows)}
        keys = sorted(k for k in expected if k not in rejected)
        got = target.target_hashes(
            ctx.run_id, ctx.namespace, ts.name, hash_expression("snowflake", hash_cols, ts.columns), keys[0], keys[-1]
        )
        hashed[ts.name] = len(keys)
        mismatched[ts.name] = {k.rstrip(" "): classes[k] or "generated" for k in keys if got.get(k) != expected[k]}
        print(f"{ts.name}: staged={len(keys)} hash_mismatch={len(mismatched[ts.name])}")
        for k, cls in sorted(mismatched[ts.name].items()):
            print(f"  {ts.name} {k} {cls}")

    assert hashed["DOCARCH"] > 2000 and hashed["FILEAUD"] > 8000 and hashed["RETNPLCY"] == len(records["RETNPLCY"])
    assert mismatched == {
        "RETNPLCY": {},
        "DOCARCH": {f"MIG04-{k:02d}": "MIG-04" for k in range(1, 6)},
        "FILEAUD": {},
    }
