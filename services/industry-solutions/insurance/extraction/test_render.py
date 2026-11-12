"""Offline seed/config drift tests; no Oracle container or SQL mutations required."""

import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from render import HERE, INSERT_ROW, INSERT_START, ROOT, SEED, validate_seed_config


class SeedConfigTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(
            (HERE / "product-config.json").read_text(), parse_float=Decimal
        )
        self.sql = SEED.read_text()

    def test_current_seed_matches(self):
        validate_seed_config(self.config, self.sql)

    def test_config_field_drift(self):
        mutations = [
            ("products", 0, "code", "OTHER"),
            ("products", 0, "name", "Changed name"),
            ("products", 0, "line", "HOME"),
            ("products", 0, "basis", "tiered"),
            ("products", 0, "default_rate_pct", 9),
            ("products", 0, "effective_from", "2024-02-01"),
            ("products", 0, "effective_to", "2026-01-01"),
            ("products", 3, "flat_reference_rate_pct", 44),
            ("products", 3, "flat_reference_from", "2020-02-01"),
            ("products", 3, "basis", "flat"),
            ("agent_overrides", 0, "product", "HOME-PLUS"),
            ("agent_overrides", 0, "agent_id", 2),
            ("agent_overrides", 0, "rate_pct", 10),
            ("agent_overrides", 0, "effective_from", "2024-07-01"),
            ("agent_overrides", 0, "effective_to", "2026-01-01"),
            ("tier_schedule", 0, "product", "AUTO-STD"),
            ("tier_schedule", 0, "tier", "T2"),
            ("tier_schedule", 0, "rate_pct", 44),
            ("tier_schedule", 0, "change_date", "2020-02-01"),
        ]
        for section, index, key, value in mutations:
            with self.subTest(section=section, index=index, key=key):
                config = copy.deepcopy(self.config)
                rows = (
                    config[section]["rows"]
                    if section == "tier_schedule"
                    else config[section]
                )
                rows[index][key] = value
                with self.assertRaisesRegex(ValueError, "Seed/config drift"):
                    validate_seed_config(config, self.sql)

    def test_seed_value_drift(self):
        mutations = [
            ("'Standard Auto'", "'Different name'"),
            ("'AUTO');", "'HOME');"),
            ("NULL, 8.00", "NULL, 9.00"),
            ("NULL, 10.00", "NULL, 11.00"),
            ("NULL, 15.00", "NULL, 16.00"),
            ("NULL, 45.00", "NULL, 44.00"),
            ("NULL, 6.00", "NULL, 5.00"),
            ("'AUTO-STD',  1,", "'AUTO-STD',  2,"),
            ("1,    9.50", "1,    9.75"),
            ("DATE '2024-06-01'", "DATE '2024-07-01'"),
            ("DATE '2024-01-01', NULL", "DATE '2024-01-01', DATE '2026-01-01'"),
            ("'T1', 45.00", "'T1', 44.00"),
            ("'T1', 40.00", "'T1', 41.00"),
            ("'T2', 30.00", "'T2', 31.00"),
            ("'T1', 6.00", "'T1', 7.00"),
            ("'T2', 4.50", "'T2', 5.00"),
            ("DATE '2025-07-01', 'rmendes'", "DATE '2025-07-02', 'rmendes'"),
        ]
        for before, after in mutations:
            with self.subTest(before=before):
                self.assertIn(before, self.sql)
                with self.assertRaisesRegex(ValueError, "Seed/config drift"):
                    validate_seed_config(
                        self.config, self.sql.replace(before, after, 1)
                    )

    def test_missing_extra_and_duplicate_seed_rows(self):
        for table in ("products", "commission_rates", "tier_rate_schedule"):
            start = next(m for m in INSERT_START.finditer(self.sql) if m[1] == table)
            match = INSERT_ROW.match(self.sql, start.start())
            if match is None:
                self.fail(f"Missing seed INSERT for {table}")
            statement = match[0]
            for sql in (
                self.sql.replace(statement, "", 1),
                self.sql + statement,
                self.sql
                + statement.replace("AUTO-STD", "UNLISTED").replace(
                    "WL-PAR", "UNLISTED"
                ),
            ):
                with (
                    self.subTest(table=table, sql_tail=sql[-100:]),
                    self.assertRaisesRegex(ValueError, "Seed/config drift"),
                ):
                    validate_seed_config(self.config, sql)

    def test_missing_extra_and_duplicate_config_rows(self):
        for section in ("products", "agent_overrides", "tier_schedule"):
            for action in ("remove", "duplicate", "extra"):
                with self.subTest(section=section, action=action):
                    config = copy.deepcopy(self.config)
                    rows = (
                        config[section]["rows"]
                        if section == "tier_schedule"
                        else config[section]
                    )
                    if action == "remove":
                        rows.pop(0)
                    else:
                        row = copy.deepcopy(rows[0])
                        if action == "extra":
                            row["code" if section == "products" else "product"] = (
                                "UNLISTED"
                            )
                        rows.append(row)
                    with self.assertRaisesRegex(ValueError, "Seed/config drift"):
                        validate_seed_config(config, self.sql)

    def test_order_comments_whitespace_and_numeric_scale_do_not_drift(self):
        sql = self.sql.replace("INSERT INTO", "insert\n into").replace(
            "VALUES", "values"
        )
        sql = sql.replace("8.00", "+8.000e0").replace("NULL", "null")
        sql = sql.replace("'Standard Auto'", "'Standard Auto, Agent''s -- /* name */'")
        sql = (
            "-- INSERT INTO products VALUES ('fake');\n/* UPDATE products SET x=1; */\n"
            + sql
        )
        config = copy.deepcopy(self.config)
        config["products"][0]["name"] = "Standard Auto, Agent's -- /* name */"
        config["products"].reverse()
        config["agent_overrides"].reverse()
        config["tier_schedule"]["rows"].reverse()
        validate_seed_config(config, sql)

    def test_column_order_does_not_drift(self):
        sql = self.sql.replace(
            "(product_code, product_name, line_of_business) VALUES\n    ('AUTO-STD',  'Standard Auto',        'AUTO')",
            "(line_of_business, product_code, product_name) VALUES ('AUTO', 'AUTO-STD', 'Standard Auto')",
        )
        self.assertNotEqual(sql, self.sql)
        validate_seed_config(self.config, sql)

    def test_paper_spec_alternatives_and_seed_metadata_are_separate(self):
        config = copy.deepcopy(self.config)
        config["chargeback"]["spec_bands"][0]["paid_commission_reversal_pct"] = 99
        config["premium_tier"]["spec"]["immutable"] = False
        sql = self.sql.replace("'seed'", "'different actor'").replace(
            "(1, 'AUTO-STD',  NULL", "(99, 'AUTO-STD',  NULL"
        )
        validate_seed_config(config, sql)

    def test_delete_with_or_without_from_fails_closed(self):
        for table in ("products", "commission_rates", "tier_rate_schedule"):
            for target in (table, f'"{table.upper()}"', f"commission_pay.{table}"):
                for from_clause in ("", "FROM "):
                    statement = f"DELETE {from_clause}{target} WHERE 1=1;"
                    with (
                        self.subTest(statement=statement),
                        self.assertRaisesRegex(ValueError, "only literal INSERT"),
                    ):
                        validate_seed_config(
                            self.config,
                            self.sql.replace("COMMIT;", statement + "\nCOMMIT;"),
                        )

    def test_unsupported_sql_fails_closed(self):
        for extra in (
            "UPDATE products SET product_name='Changed';",
            "DELETE FROM commission_rates;",
            "MERGE INTO tier_rate_schedule USING other ON (1=1);",
            "TRUNCATE TABLE products;",
            "INSERT ALL INTO products VALUES ('x') SELECT 1 FROM dual;",
            "INSERT INTO products (product_code) SELECT 'OTHER' FROM dual;",
            "INSERT INTO products (product_code) VALUES (UPPER('OTHER'));",
            "INSERT INTO products (product_code) VALUES ('broken);",
            "INSERT INTO products (product_code) VALUES (,'OTHER');",
            "INSERT INTO products (product_code) VALUES ('a', 'b');",
            "INSERT INTO products (product_code, product_code) VALUES ('a', 'b');",
            "INSERT INTO \"PRODUCTS\" (product_code) VALUES ('OTHER');",
            "UPDATE \"PRODUCTS\" SET product_name='Other';",
        ):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                validate_seed_config(self.config, self.sql + extra)

    def test_cli_fails_before_overwriting_catalogs_even_with_python_optimization(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            files = {
                p for p in HERE.iterdir() if p.suffix in {".json", ".md", ".csv", ".py"}
            }
            for rule in json.loads((HERE / "rules.json").read_text()):
                files.update(ROOT / s["file"] for s in rule["sources"])
            files.add(SEED)
            for src in files:
                dst = root / src.relative_to(ROOT)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            here = root / HERE.relative_to(ROOT)
            command = [sys.executable, "-O", str(here / "render.py")]
            good = subprocess.run(command, text=True, capture_output=True, check=False)
            self.assertEqual(good.returncode, 0, good.stderr)
            catalogs = {
                name: (here / name).read_bytes()
                for name in ("catalog.md", "catalog.csv", "sign-off.md")
            }
            config_path = here / "product-config.json"
            original = config_path.read_text()
            for before, after in (
                ('"default_rate_pct": 8,', '"default_rate_pct": 9,'),
                (
                    '"default_rate_pct": 8,',
                    '"default_rate_pct": 8.00000000000000000001,',
                ),
            ):
                with self.subTest(after=after):
                    self.assertIn(before, original)
                    config_path.write_text(original.replace(before, after, 1))
                    bad = subprocess.run(
                        command, text=True, capture_output=True, check=False
                    )
                    self.assertNotEqual(bad.returncode, 0)
                    self.assertIn("Seed/config drift in commission_rates", bad.stderr)
                    for name, contents in catalogs.items():
                        self.assertEqual((here / name).read_bytes(), contents)
            config_path.write_text(original)
            seed_path = root / SEED.relative_to(ROOT)
            seed_path.write_text(self.sql.replace("NULL, 8.00", "NULL, 9.00", 1))
            bad_seed = subprocess.run(
                command, text=True, capture_output=True, check=False
            )
            self.assertNotEqual(bad_seed.returncode, 0)
            self.assertIn("Seed/config drift in commission_rates", bad_seed.stderr)
            for name, contents in catalogs.items():
                self.assertEqual((here / name).read_bytes(), contents)


if __name__ == "__main__":
    unittest.main()
