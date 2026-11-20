import hashlib
import json
import os
import sys
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "services/odl-sources"))
from odl_sources import generate as g


class GeneratorTests(unittest.TestCase):
    def test_bytes_and_seed(self):
        def digest(seed):
            settings = g.Settings(seed=seed, db2_customers=100, db2_history=800,
                                  oracle_accounts=80, pg_contacts=60)
            return hashlib.sha256("".join(g.records(settings)).encode()).hexdigest()
        self.assertEqual(digest("42"), digest("42"))
        self.assertNotEqual(digest("42"), digest("43"))

    def test_sizes(self):
        s = g.Settings()
        self.assertEqual(sum(1 for _ in g.customers(s)), 50000)
        self.assertEqual(sum(1 for _ in g.history(s)), 400000)
        self.assertEqual(sum(1 for _ in g.accounts(s)), 40000)
        self.assertEqual(sum(1 for _ in g.products()), 4)
        self.assertEqual(sum(1 for _ in g.contacts(s)), 30000)
        self.assertEqual(sum(1 for _ in g.cases(s)), 60000)
        self.assertEqual(sum(1 for _ in g.subscriptions(s)), 30000)

    def test_empty_invalid_and_environment(self):
        s = g.Settings(db2_customers=0, db2_history=0, oracle_accounts=0, pg_contacts=0)
        self.assertEqual(list(g.customers(s)), [])
        self.assertEqual(list(g.history(s)), [])
        self.assertEqual(list(g.accounts(s)), [])
        self.assertEqual(list(g.contacts(s)), [])
        self.assertEqual(list(g.cases(s)), [])
        for params in ({"db2_customers": -1}, {"db2_customers": 0}, {"dup_rate": 1}):
            with self.assertRaises(ValueError):
                g.Settings(**params)
        with patch.dict(os.environ, {"ODL_SEED": "7", "ODL_PG_CONTACTS": "12"}):
            self.assertEqual(g.Settings.environment().pg_contacts, 12)
            self.assertEqual(g.Settings.environment().seed, "7")
        with patch.dict(os.environ, {"ODL_DB2_HISTORY": "no"}):
            with self.assertRaises(ValueError):
                g.Settings.environment()

    def test_source_cohorts(self):
        s = g.Settings()
        regional = list(g.accounts(s))[:s.shared_count]
        changed = [i for i, row in enumerate(regional)
                   if (row["holder_name"], row["address"]) != g.person(s, i)]
        self.assertEqual(len(changed), 600)
        self.assertAlmostEqual(len(changed) / s.shared_count, 0.02, delta=0.001)
        ids = {r["contact_id"] for r in g.contacts(s)}
        self.assertTrue(all(g.contact_id(s, i) not in ids for i in changed))
        self.assertTrue(all(g.contact_id(s, i) in ids for i in range(600, 30000)))
        self.assertNotEqual(g.customer_no(600).strip(), str(regional[600]["account_id"]))

    def test_customer_columns(self):
        s = g.Settings()
        rows = list(g.customers(s))
        self.assertEqual(sum(len(r["cust_no"]) == 10 and r["cust_no"].endswith("  ") for r in rows), 50000)
        self.assertEqual(sum(r["opened_on"] == "0001-01-01" for r in rows), 500)
        self.assertTrue(all(r["opened_ymd"] == int(r["opened_on"].replace("-", "")) for r in rows))
        raw = [bytes.fromhex(r["full_name"]) for r in rows]
        self.assertEqual(sum("\ufffd" in r.decode("utf-8", errors="replace") for r in raw), 500)
        self.assertIn("José", raw[0].decode("cp037"))

    def test_account_and_crm_columns(self):
        s = g.Settings()
        rows = list(g.accounts(s))
        self.assertEqual(sum(r["opened_at"].startswith(("2024-03-10", "2024-11-03")) for r in rows), 4)
        self.assertTrue(all(Decimal(r["balance"]).as_tuple().exponent == -2 for r in rows))
        self.assertEqual(sum(r["credit"] == 0.1 + 0.2 for r in g.contacts(s)), 600)
        sql = (ROOT / "services/odl-sources/postgres/ddl.sql").read_text().upper()
        self.assertIn("DOUBLE PRECISION", sql)
        self.assertNotIn("CREATE INDEX", sql)
        self.assertEqual(sum(r["status"] == "active" for r in g.subscriptions(s)), 30000)
        self.assertIn('subscription_status=row["status"]', (ROOT / "services/billing-service/app/repository.py").read_text())
        self.assertIn('"subscription_status": row.subscription_status', (ROOT / "services/billing-service/app/main.py").read_text())

    def test_manifest_contract(self):
        manifest = json.loads((ROOT / "demos/app/complexity-manifest.json").read_text())
        self.assertEqual({r["id"] for r in manifest["classes"]}, {f"MIG-{i:02}" for i in range(1, 8)})
        self.assertEqual({r["id"] for r in manifest["odl"]["classes"]}, {f"ODL-{i:02}" for i in range(1, 10)})
        incident = next(row for row in manifest["odl"]["classes"] if row["id"] == "ODL-09")
        self.assertEqual(incident["replay"], [f"scripts/odl/scenario.sh {command} odl-read-latency"
                                             for command in ("disarm", "reset", "arm")])
        for row in manifest["odl"]["classes"]:
            self.assertTrue(all(k in row for k in ("source", "table", "field", "query", "expected_count")))


if __name__ == "__main__":
    unittest.main()
