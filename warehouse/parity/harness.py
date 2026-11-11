"""Idempotent setup on the isolated after-side database."""
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'snowflake'))
from sfx_conn import connect, query_tag
from .inventory import BOOTSTRAP, ESTATE, inventory, landing_sources, table_definitions

DATABASE = "SFX_D1110_AFTER"
COMMENT = "run_token=sfx-d1110 expires=2026-11-24"
def control_table():
    schema = os.environ.get('PC_CONTROL_SCHEMA', 'MIGRATION_CONTROL').upper()
    table = os.environ.get('PC_CONTROL_TABLE', 'MAPPINGS').upper()
    if not re.fullmatch(r'[A-Z][A-Z0-9_]*', schema):
        raise ValueError('Invalid PC_CONTROL_SCHEMA')
    if not re.fullmatch(r'[A-Z][A-Z0-9_]*', table):
        raise ValueError('Invalid PC_CONTROL_TABLE')
    return f'{DATABASE}.{schema}.{table}'
DESCRIPTIVE = ["folder", "mapping", "workflow", "session_name", "source_objects",
               "target_table", "dbt_model", "patterns", "owner_effort"]
ACT3_CONTENT = {'m_SFX_APP_USER', 'm_SFX_STG_APP_USER', 'm_SFX_DOCUMENT',
                'm_SFX_STG_DOCUMENT', 'm_SFX_DOC_SHARE'}


def owner_effort(row):
    return ('act3-workflow' if row['folder'] == 'SFX_BILLING' or
            row['mapping'] in ACT3_CONTENT else 'migrations-page')


def require_owner(cursor, mapping, owner='act3-workflow', folder=None):
    cursor.execute('SELECT FOLDER, OWNER_EFFORT FROM IDENTIFIER(%s) WHERE MAPPING=%s', (control_table(), mapping))
    rows = cursor.fetchall()
    if len(rows) != 1 or rows[0][-1] != owner:
        raise ValueError(f'Mapping ownership mismatch: {mapping} (requested {owner})')
    if folder is not None and rows[0][0] != folder:
        raise ValueError(f'Mapping folder mismatch: {mapping} (requested {folder})')


def tag(step, mapping=None):
    return dict(run="sfx-d1110", act="scale", step=step,
                **({"mapping": mapping} if mapping else {}))


def connection(workload, step, mapping=None):
    if os.environ.get("SNOWFLAKE_DATABASE") != DATABASE:
        raise ValueError("SNOWFLAKE_DATABASE must be SFX_D1110_AFTER")
    return connect(workload, "parity_" + step, extra_tag=tag(step, mapping))


def control_ddl():
    return f"""CREATE TABLE IF NOT EXISTS {control_table()} (
        FOLDER VARCHAR, MAPPING VARCHAR, WORKFLOW VARCHAR, SESSION_NAME VARCHAR,
        SOURCE_OBJECTS VARCHAR, TARGET_TABLE VARCHAR, DBT_MODEL VARCHAR, PATTERNS VARCHAR,
        BEFORE_ROWS NUMBER, AFTER_ROWS NUMBER, ROWCOUNT_MATCH BOOLEAN, KEYED_HASH_MATCH BOOLEAN,
        SAMPLED_DIFFS VARIANT, RUN1_ROWS NUMBER, RUN2_ROWS NUMBER, RERUN_DUPLICATES NUMBER,
        STATUS VARCHAR DEFAULT 'PENDING', AMBER_REASON VARCHAR, PR_URL VARCHAR,
        PARITY_QUERY_TAG VARCHAR, VERIFIED_AT TIMESTAMP_TZ, OWNER_EFFORT VARCHAR
    ) COMMENT = '{COMMENT}'"""


def merge_sql():
    columns = ', '.join(DESCRIPTIVE)
    select = ', '.join('%s AS ' + c for c in DESCRIPTIVE)
    return f"""MERGE INTO {control_table()} t USING (SELECT {select}) s
        ON t.folder=s.folder AND t.mapping=s.mapping
        WHEN MATCHED AND t.owner_effort IS NULL THEN UPDATE SET t.owner_effort=s.owner_effort
        WHEN NOT MATCHED THEN INSERT ({columns}, STATUS)
        VALUES ({', '.join('s.' + c for c in DESCRIPTIVE)}, 'PENDING')"""


def source_plan(landing):
    definitions = table_definitions()
    plan = []
    for table, (area, relative) in sorted(landing_sources().items()):
        candidates = [body for name, body in definitions.items()
                      if name.split('.')[1] == 'STG_' + table]
        if len(candidates) != 1:
            raise ValueError(f"No unique staging DDL for {table}")
        path = landing / relative
        if not path.is_file():
            raise FileNotFoundError(path)
        plan.append((table, candidates[0], path))
    return plan


def setup(landing=None, skip_control=False):
    rows = inventory()
    landing = landing or Path(os.environ.get("LANDING_DIR", ESTATE / "tests/fixture/landing"))
    plan = source_plan(landing)
    definitions = table_definitions()
    seeds = re.findall(r"INSERT INTO (\w+\.\w+) (.*?)ON CONFLICT DO NOTHING;",
                       BOOTSTRAP.read_text(), re.S)
    with connection("load", "setup") as conn, conn.cursor() as cur:
        for schema in ("PC_SRC", "PC_BEFORE", "PC_BILLING", "PC_CONTENT", "PC_AUDIT"):
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {DATABASE}.{schema} COMMENT = '{COMMENT}'")
        stage = DATABASE + ".PC_SRC.LANDING_STAGE"
        cur.execute(f"CREATE STAGE IF NOT EXISTS {stage} COMMENT = '{COMMENT}'")
        for table, body, path in plan:
            relation = DATABASE + '.PC_SRC.' + table
            cur.execute(f"CREATE TABLE IF NOT EXISTS {relation} ({body}) COMMENT = '{COMMENT}'")
            uri = path.resolve().as_uri().replace("'", "''")
            cur.execute(f"PUT '{uri}' @{stage}/{table}/ AUTO_COMPRESS=FALSE OVERWRITE=TRUE")
            cur.execute(f"TRUNCATE TABLE {relation}")
            cur.execute(f"""COPY INTO {relation} FROM @{stage}/{table}/
                FILES = ('20261109.psv') FILE_FORMAT = (TYPE=CSV FIELD_DELIMITER='|'
                SKIP_HEADER=0 FIELD_OPTIONALLY_ENCLOSED_BY=NONE EMPTY_FIELD_AS_NULL=TRUE
                NULL_IF=('') ESCAPE_UNENCLOSED_FIELD=NONE) FORCE=TRUE ON_ERROR=ABORT_STATEMENT""")
            cur.execute(f"SELECT COUNT(*) FROM {relation}")
            print(f"PC_SRC.{table}: {cur.fetchone()[0]} rows")
        for source, insert in seeds:
            table = source.split('.')[1]
            if table in landing_sources():
                raise ValueError(f"Seed and landing collision: {table}")
            relation = DATABASE + '.PC_SRC.' + table
            cur.execute(f"CREATE TABLE IF NOT EXISTS {relation} ({definitions[source]}) COMMENT = '{COMMENT}'")
            cur.execute(f"TRUNCATE TABLE {relation}")
            cur.execute(f"INSERT INTO {relation} {insert}")
            cur.execute(f"SELECT COUNT(*) FROM {relation}")
            print(f"PC_SRC.{table}: {cur.fetchone()[0]} rows (bootstrap reference seed)")
        if skip_control:
            print('Control setup skipped; PC_SRC load complete')
            return
        try:
            cur.execute(control_ddl())
            cur.execute(f'ALTER TABLE {control_table()} ADD COLUMN IF NOT EXISTS OWNER_EFFORT VARCHAR')
            for row in rows:
                values = [row['folder'], row['mapping'], row['workflow'], row['session'],
                          json.dumps(row['source_objects']), row['target_table'], row['dbt_model'],
                          ','.join(row['patterns']), owner_effort(row)]
                cur.execute(merge_sql(), values)
        except Exception as error:
            raise RuntimeError(f'PC_SRC loaded; control setup failed at {control_table()}. '
                               'Check schema access or set PC_CONTROL_SCHEMA.') from error
    print(f"Inventory: {len(rows)} mappings seeded; existing results preserved")


def licence():
    with connection("ops", "licence") as conn, conn.cursor() as cur:
        cur.execute(f"SELECT OWNER_EFFORT, STATUS, COUNT(*) FROM {control_table()} GROUP BY OWNER_EFFORT, STATUS")
        records = cur.fetchall()
    counts = {}
    owners = {}
    for owner, status, count in records:
        counts[status] = counts.get(status, 0) + count
        owners.setdefault(owner or 'UNASSIGNED', {})[status] = count
    total = sum(counts.values())
    print(f"Total mappings: {total}")
    for status in ("VERIFIED", "AMBER", "PENDING"):
        print(f"{status}: {counts.get(status, 0)}")
    print(f"PowerCenter mappings remaining: {total - counts.get('VERIFIED', 0)}")
    for owner, values in sorted(owners.items()):
        total = sum(values.values())
        print(f"{owner}: total={total} VERIFIED={values.get('VERIFIED', 0)} "
              f"AMBER={values.get('AMBER', 0)} PENDING={values.get('PENDING', 0)} "
              f"remaining={total - values.get('VERIFIED', 0)}")
