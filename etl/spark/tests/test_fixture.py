import contextlib
import csv
from decimal import Decimal
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    "generate_fixture", Path(__file__).resolve().parents[1] / "fixture/generate_fixture.py"
)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fixture"))
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


class FixtureTest(unittest.TestCase):
    def test_startup_uses_spark_fixture(self):
        root = Path(__file__).resolve().parents[3]
        for landing in ("etl/spark/.data/landing", "/custom/landing"):
            with self.subTest(landing=landing):
                result = subprocess.run(
                    ["make", "-n", "sfx-spark-up", f"SFX_SPARK_LANDING={landing}"],
                    cwd=root, capture_output=True, text=True, check=True,
                )
                output = str((root / landing).resolve())
                self.assertIn(
                    f"python3 etl/spark/fixture/generate_fixture.py --rows 200000 --seed 1110 --output {output}",
                    result.stdout,
                )
                self.assertIn(f"LANDING_DIR={output}", result.stdout)
                self.assertNotIn("warehouse/seed/generate.py", result.stdout)
                self.assertNotIn("warehouse/landing", result.stdout)

    def generate(self, path, rows):
        with contextlib.redirect_stdout(io.StringIO()):
            fixture.generate(path, rows, 1110)

    def test_tables_and_repeatability(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.generate(root, 100)
            files = sorted(root.rglob("*.psv"))
            self.assertEqual(len(fixture.SCHEMAS), 42)
            self.assertEqual(len(files), 78)
            before = {p: p.read_bytes() for p in files}
            self.generate(root, 100)
            self.assertEqual(before, {p: p.read_bytes() for p in files})
            for area, tables in fixture.TABLES.items():
                for table in tables:
                    records = []
                    for path in (root / area / table).glob("*.psv"):
                        with path.open() as stream:
                            records.extend(csv.DictReader(stream, delimiter="|"))
                    self.assertEqual(len(records), min(100, fixture.DIMENSION_ROWS.get(table, 100)))
                    self.assertEqual(set(records[0]), {name for name, _ in fixture.SCHEMAS[table]})

    def test_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.generate(root, 0)
            for path in root.rglob("*.psv"):
                self.assertEqual(len(path.read_text().splitlines()), 1)

    def test_invalid_rows(self):
        with self.assertRaisesRegex(ValueError, "nonnegative"):
            self.generate(Path("."), -1)

    def test_journal_balance(self):
        for rows in (1, 5, 100):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.generate(root, rows)
                totals = {}
                with (root / "billing/GL_JOURNAL_LINE/20261109.psv").open() as stream:
                    for row in csv.DictReader(stream, delimiter="|"):
                        key = row["JOURNAL_ID"], row["CURRENCY_CODE"], row["POSTING_DATE"]
                        totals[key] = totals.get(key, Decimal(0)) + Decimal(row["DEBIT_AMT"]) - Decimal(row["CREDIT_AMT"])
                self.assertTrue(all(amount == 0 for amount in totals.values()))

    def test_business_values(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.generate(root, 100)
            with (root / "billing/CUSTOMER_ACCOUNT/20261109.psv").open() as stream:
                accounts = list(csv.DictReader(stream, delimiter="|"))
            self.assertTrue(all(row["ACCOUNT_NUMBER"].startswith("ACC-") for row in accounts))
            self.assertGreater(len({row["CURRENCY_CODE"] for row in accounts}), 4)
            with (root / "users/APP_USER/20261109.psv").open() as stream:
                users = list(csv.DictReader(stream, delimiter="|"))
            self.assertTrue(all(" " in row["DISPLAY_NAME"] for row in users))
            self.assertTrue(all(row["EMAIL"].endswith(".example") for row in users))
            companies = {row["OWNER_USER_ID"]: row["ACCOUNT_NAME"] for row in accounts}
            for user in users:
                self.assertEqual(
                    user["EMAIL"].split("@")[1],
                    companies[user["USER_ID"]].lower().replace(" ", "-") + ".example",
                )
            with (root / "users/TEAM/20261109.psv").open() as stream:
                teams = list(csv.DictReader(stream, delimiter="|"))
            self.assertGreater(len({row["TEAM_NAME"] for row in teams}), 12)
            self.assertTrue(all(not row["TEAM_NAME"].endswith("- Bramble") for row in teams))

    def test_email_collisions(self):
        emails = fixture.user_emails(5000)
        self.assertEqual(len(set(emails.values())), 5000)
        seen = set()
        collisions = 0
        for i, email in emails.items():
            first, last = fixture.person(i)
            domain = fixture.company(i).lower().replace(" ", "-") + ".example"
            base = f"{first.lower()}.{last.lower()}@{domain}"
            if base not in seen:
                self.assertEqual(email, base)
                seen.add(base)
            else:
                collisions += 1
                self.assertNotEqual(email, base)
                self.assertTrue(email.split("@")[0][-1].isdigit())
        self.assertGreater(collisions, 0)
        self.assertEqual(fixture.user_emails(0), {})
