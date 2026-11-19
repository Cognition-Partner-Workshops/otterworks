import csv
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "fixture"))
from generate_fixture import generate
from initialize import load_sql
from common.schemas import SCHEMAS, TABLES


class InitializeTest(unittest.TestCase):
    def test_load_sql(self):
        with tempfile.TemporaryDirectory() as directory:
            landing = Path(directory)
            generate(landing, 3, 1110)
            sql = load_sql(landing)
            self.assertTrue(sql.startswith("BEGIN;\n"))
            self.assertTrue(sql.endswith("COMMIT;\n"))
            for area, tables in TABLES.items():
                for table in tables:
                    for path in (landing / area / table).glob("*.psv"):
                        with path.open() as stream:
                            rows = list(csv.reader(stream, delimiter="|"))
                        self.assertEqual(rows[0], [name for name, _ in SCHEMAS[table]])
                        self.assertTrue(all(len(row) == len(rows[0]) for row in rows))
                        self.assertIn(f"/opt/landing/{area}/{table}/{path.name}", sql)
            self.assertEqual(sql.count("HEADER true"), sql.count("COPY "))

    def test_empty_tables(self):
        with tempfile.TemporaryDirectory() as directory:
            landing = Path(directory)
            generate(landing, 0, 1110)
            self.assertIn("COMMIT;", load_sql(landing))

    def test_missing_files(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "No landing files"):
                load_sql(Path(directory))


if __name__ == "__main__":
    unittest.main()
