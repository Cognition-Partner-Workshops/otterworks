"""The Oracle catalog (migration/source/oracle/catalog) covers every object the seed DDL creates.

No Oracle needed: the seed DDL (migration/source/oracle/ddl) is parsed for the objects it creates -
users, tables, their primary-key indexes, indexes, views, packages and package bodies, sequences,
triggers and scheduler jobs - and each must have exactly one <OWNER>.<OBJECT_TYPE>.<NAME>.sql file
in the catalog, listed in INVENTORY.json with a matching SHA-256 (the files are DBMS_METADATA output,
never hand-edited) and a row in the ASSESSMENT.md port matrix. A catalog file with no seed object
fails too, so the catalog cannot drift in either direction.

python3.12 -m unittest seed.test_oracle_catalog -v
"""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path

ORACLE_DIR = Path(__file__).resolve().parents[1] / "oracle"
DDL_DIR = ORACLE_DIR / "ddl"
CATALOG_DIR = ORACLE_DIR / "catalog"

_IDENT = r'"?([A-Z][A-Z0-9_$#]*)"?'
_CREATE_RE = re.compile(
    r"\bCREATE\s+(?:OR\s+REPLACE\s+)?(?:(?:NON)?EDITIONABLE\s+)?(?:FORCE\s+)?(?:UNIQUE\s+|BITMAP\s+)?"
    r"(TABLE|VIEW|SEQUENCE|TRIGGER|INDEX|PACKAGE\s+BODY|PACKAGE)\s+" + _IDENT + r"\." + _IDENT,
    re.IGNORECASE,
)
_CREATE_USER_RE = re.compile(r"\bCREATE\s+USER\s+" + _IDENT, re.IGNORECASE)
_CREATE_JOB_RE = re.compile(
    r"\bDBMS_SCHEDULER\.CREATE_JOB\s*\(\s*(?:job_name\s*=>\s*)?'" + _IDENT + r"\." + _IDENT + r"'",
    re.IGNORECASE,
)
_KEY_CONSTRAINT_RE = re.compile(r"\bCONSTRAINT\s+" + _IDENT + r"\s+(?:PRIMARY\s+KEY|UNIQUE)\b", re.IGNORECASE)
_CATALOG_FILE_RE = re.compile(r"^([A-Z0-9_$#]+)\.([A-Z_]+)\.([A-Z0-9_$#]+)\.sql$")
_MATRIX_ROW_RE = re.compile(r"^\|\s*`([A-Z0-9_$#]+)\.([A-Z0-9_$#]+)`\s*\|\s*([A-Z ]+?)\s*\|", re.MULTILINE)


def _strip_comments(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    return re.sub(r"--[^\n]*", " ", sql)


def _table_body(sql: str, start: int) -> str:
    """Text of the parenthesised column list that follows position `start` (the CREATE TABLE match end)."""
    open_at = sql.index("(", start)
    depth = 0
    for i in range(open_at, len(sql)):
        if sql[i] == "(":
            depth += 1
        elif sql[i] == ")":
            depth -= 1
            if depth == 0:
                return sql[open_at : i + 1]
    raise ValueError("unbalanced CREATE TABLE")


def seed_objects(ddl_dir: Path = DDL_DIR) -> set[tuple[str, str, str]]:
    """(owner, object_type, name) for every object the seed DDL creates, object_type as in DBA_OBJECTS."""
    found: set[tuple[str, str, str]] = set()
    for path in sorted(ddl_dir.glob("*.sql")):
        sql = _strip_comments(path.read_text(encoding="utf-8"))
        for m in _CREATE_USER_RE.finditer(sql):
            found.add((m.group(1).upper(), "USER", m.group(1).upper()))
        for m in _CREATE_RE.finditer(sql):
            kind = " ".join(m.group(1).upper().split())
            owner, name = m.group(2).upper(), m.group(3).upper()
            found.add((owner, kind, name))
            if kind == "TABLE":
                for c in _KEY_CONSTRAINT_RE.finditer(_table_body(sql, m.end())):
                    found.add((owner, "INDEX", c.group(1).upper()))
        for m in _CREATE_JOB_RE.finditer(sql):
            found.add((m.group(1).upper(), "JOB", m.group(2).upper()))
    return found


def catalog_objects(catalog_dir: Path = CATALOG_DIR) -> set[tuple[str, str, str]]:
    found = set()
    for path in catalog_dir.iterdir():
        m = _CATALOG_FILE_RE.match(path.name)
        if m:
            found.add((m.group(1), m.group(2).replace("_", " "), m.group(3)))
    return found


def catalog_file(owner: str, kind: str, name: str) -> Path:
    return CATALOG_DIR / f"{owner}.{kind.replace(' ', '_')}.{name}.sql"


class SeedParserTest(unittest.TestCase):
    def test_parser_sees_every_statement_kind(self):
        ddl = """
        -- CREATE TABLE ARCHIVE.COMMENTED_OUT (X NUMBER);
        CREATE USER ARCHIVE NO AUTHENTICATION;
        CREATE TABLE ARCHIVE.T1 (A CHAR(4), B NUMBER(3, 0), CONSTRAINT PK_T1 PRIMARY KEY (A),
            CONSTRAINT CK_T1 CHECK (B IN (1, 2)));
        CREATE UNIQUE INDEX ARCHIVE.UX_T1 ON ARCHIVE.T1 (B);
        CREATE OR REPLACE FORCE VIEW ARCHIVE.V1 AS SELECT A FROM ARCHIVE.T1;
        CREATE OR REPLACE PACKAGE ARCHIVE.P1 AS END;
        /
        CREATE OR REPLACE PACKAGE BODY ARCHIVE.P1 AS END;
        /
        CREATE SEQUENCE ARCHIVE.S1;
        CREATE OR REPLACE TRIGGER ARCHIVE.TR1 AFTER UPDATE ON ARCHIVE.T1 BEGIN NULL; END;
        /
        BEGIN DBMS_SCHEDULER.CREATE_JOB(job_name => 'ARCHIVE.J1', job_type => 'PLSQL_BLOCK'); END;
        /
        """
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "001.sql").write_text(ddl, encoding="utf-8")
            got = seed_objects(Path(tmp))
        self.assertEqual(
            got,
            {
                ("ARCHIVE", "USER", "ARCHIVE"),
                ("ARCHIVE", "TABLE", "T1"),
                ("ARCHIVE", "INDEX", "PK_T1"),
                ("ARCHIVE", "INDEX", "UX_T1"),
                ("ARCHIVE", "VIEW", "V1"),
                ("ARCHIVE", "PACKAGE", "P1"),
                ("ARCHIVE", "PACKAGE BODY", "P1"),
                ("ARCHIVE", "SEQUENCE", "S1"),
                ("ARCHIVE", "TRIGGER", "TR1"),
                ("ARCHIVE", "JOB", "J1"),
            },
        )

    def test_seed_ddl_creates_the_known_estate(self):
        kinds = {kind for _, kind, _ in seed_objects()}
        self.assertEqual(
            kinds, {"USER", "TABLE", "INDEX", "VIEW", "PACKAGE", "PACKAGE BODY", "SEQUENCE", "TRIGGER", "JOB"}
        )
        self.assertIn(("ARCHIVE", "PACKAGE BODY", "RETENTION_PKG"), seed_objects())
        self.assertIn(("MIGAUDIT", "INDEX", "PK_PURGE_LOG"), seed_objects())


class CatalogCoverageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed = seed_objects()
        cls.catalog = catalog_objects()
        cls.inventory = json.loads((CATALOG_DIR / "INVENTORY.json").read_text(encoding="utf-8"))

    def test_every_seed_object_has_a_catalog_file(self):
        missing = sorted(self.seed - self.catalog)
        self.assertEqual(missing, [], "seed DDL creates objects with no catalog file; re-run catalog/extract.py")

    def test_every_catalog_file_is_a_seed_object(self):
        stale = sorted(self.catalog - self.seed)
        self.assertEqual(stale, [], "catalog files for objects the seed DDL no longer creates")

    def test_catalog_file_declares_its_object(self):
        for owner, kind, name in sorted(self.catalog):
            ddl = catalog_file(owner, kind, name).read_text(encoding="utf-8")
            if kind == "USER":
                needle = rf'CREATE\s+USER\s+"{name}"'
            elif kind == "JOB":
                needle = rf"dbms_scheduler\.create_job\('\"{name}\"'"
            else:
                needle = rf'\bCREATE\b.*\b{kind}\s+"{owner}"\."{name}"'
            with self.subTest(file=catalog_file(owner, kind, name).name):
                self.assertRegex(ddl, needle)

    def test_inventory_lists_each_file_with_its_hash(self):
        catalogued = {
            (e["owner"], e["object_type"], e["object_name"]): e for e in self.inventory["objects"] if e["catalogued"]
        }
        self.assertEqual(set(catalogued), self.catalog)
        for key, entry in sorted(catalogued.items()):
            path = catalog_file(*key)
            with self.subTest(file=path.name):
                self.assertEqual(entry["file"], path.name)
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), entry["sha256"])

    def test_inventory_accounts_for_every_dba_objects_row(self):
        by_type: dict[str, dict[str, int]] = {}
        for e in self.inventory["objects"]:
            if e["object_type"] == "USER":
                continue
            per_owner = by_type.setdefault(e["owner"], {})
            per_owner[e["object_type"]] = per_owner.get(e["object_type"], 0) + 1
            if not e["catalogued"]:
                self.assertTrue(e.get("reason"), e)
        self.assertEqual(by_type, self.inventory["dba_objects_by_type"])

    def test_assessment_matrix_has_a_row_per_catalogued_object(self):
        text = (CATALOG_DIR / "ASSESSMENT.md").read_text(encoding="utf-8")
        rows = {(o, " ".join(k.split()), n) for o, n, k in _MATRIX_ROW_RE.findall(text)}
        missing = sorted(self.catalog - rows)
        self.assertEqual(missing, [], "ASSESSMENT.md port matrix is missing catalogued objects")
        self.assertEqual(sorted(rows - self.catalog), [], "ASSESSMENT.md matrix rows with no catalog file")


if __name__ == "__main__":
    unittest.main()
