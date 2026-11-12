"""Offline contracts for the lineage engine and pinned schema resolver."""
import copy
from decimal import Decimal
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import yaml
from common import ROOT, lineage, records
from compare import evaluate, main as compare_main, transform
from schema_check import validator, main as schema_main


class RulesTest(unittest.TestCase):
    def setUp(self):
        self.data = lineage()

    def apply(self, name, value):
        return transform(value, self.data["rules"][name], self.data, {})

    def test_dates_decimals_codes(self):
        self.assertEqual(self.apply("date", "20240229"), "2024-02-29")
        self.assertEqual(self.apply("decimal-2", "000000000001234"), Decimal("12.34"))
        self.assertEqual(self.apply("decimal-6", "000000001234567890"), Decimal("1234.567890"))
        for code, status in [("00", 200), ("04", 404), ("08", 400), ("96", 503)]:
            self.assertEqual(self.apply("status", code), status)
        self.assertEqual(self.apply("qualification", "ROTH"), "Roth IRA")
        self.assertEqual(self.apply("policy-status", "IF"), "ACTIVE")

    def test_invalid_and_empty(self):
        for name, value in [("date", "20240230"), ("date", ""), ("decimal-2", "12.34"),
                            ("integer", "-1"), ("qualification", "UNKNOWN"), ("status", "99")]:
            with self.subTest(name=name, value=value), self.assertRaises((ValueError, KeyError)):
                self.apply(name, value)
        with patch("common.ROOT", ROOT / "parity/nonexistent-test-input"):
            with self.assertRaisesRegex(ValueError, "No frozen records"):
                records("summary")

    def fund_record(self):
        body = {"RTN_CD": "00", "CNTR_NO": "42", "FUND_CNT": "2"}
        for i in (1, 2):
            for key, value in {"FUND_CD": f"F{i}", "FUND_NM": f"Fund {i}", "UNIT_VAL": "000000002500000",
                               "FUND_VAL": "000000000001234", "FUND_UNITS": "000000000001000000",
                               "ALLOC_PCT": "05000"}.items():
                body[f"{key}_{i:02}"] = value
        return {"operation": "funds", "contract": "42", "status": 200, "body": body}

    def test_array_paging_and_missing_value(self):
        record = self.fund_record()
        actual = {"startIndex": 1, "itemsCount": 1, "totalItemsCount": 2,
                  "funds": [{"fundId": "F2", "fundName": "Fund 2", "fundPrice": 2.5, "totalFundValue": 12.34,
                             "fundSegments": [{"numberOfUnits": 1}]}]}
        result = evaluate(record, self.data, actual, 200, start=1, limit=1)
        self.assertFalse([r for r in result if r["result"] == "fail"])
        self.assertTrue([r for r in result if r["result"] == "sign-off"])
        del actual["funds"][0]["fundPrice"]
        self.assertTrue([r for r in evaluate(record, self.data, actual, 200, start=1, limit=1) if r["result"] == "fail"])
        record["body"]["FUND_NM_03"] = "Extra"
        self.assertTrue([r for r in evaluate(record, self.data, dry=True) if r["result"] == "fail"])

    def test_empty_funds_and_status_error(self):
        record = {"operation": "funds", "contract": "42", "status": 200,
                  "body": {"RTN_CD": "00", "CNTR_NO": "42", "FUND_CNT": "0"}}
        actual = {"startIndex": 0, "itemsCount": 0, "totalItemsCount": 0, "funds": []}
        self.assertFalse([r for r in evaluate(record, self.data, actual, 200) if r["result"] == "fail"])
        record["body"] = {"RTN_CD": "04"}
        self.assertFalse([r for r in evaluate(record, self.data, {}, 404) if r["result"] == "fail"])
        self.assertTrue([r for r in evaluate(record, self.data, {}, 200) if r["result"] == "fail"])

    def test_dry_signoff_is_not_pass_and_malformed_fails(self):
        record = self.fund_record()
        result = evaluate(record, self.data, dry=True)
        self.assertFalse([r for r in result if r["result"] in ("fail", "pass")])
        signoff = next(r for r in result if r["field"] == "FUND_UNITS_NN")
        self.assertEqual(signoff["transformed"][0]["value"], "1.000000")
        omitted = [r for r in result if r["result"] == "omitted-optional"]
        self.assertTrue(omitted)
        self.assertTrue(all(r["result"] == "omitted-optional" for r in result
                            if r["iri"].startswith("funds[].fundSegments[]")))
        self.assertEqual(sum(r["result"] == "sign-off" and "fundSegments" in r["iri"]
                             for r in result), 1)
        live = evaluate(record, self.data, {"startIndex": 2, "itemsCount": 0, "totalItemsCount": 2,
                                          "funds": []}, 200, start=2)
        self.assertEqual(sum(r["result"] == "omitted-optional" for r in live), len(omitted))
        record["body"]["FUND_VAL_01"] = ""
        self.assertTrue([r for r in evaluate(record, self.data, dry=True) if r["result"] == "fail"])

    def test_compare_main_offline_and_transport_failure(self):
        record = self.fund_record()
        with patch("compare.records", return_value=[record]), patch("compare.write_report") as report:
            with patch("sys.argv", ["compare.py", "--op", "funds", "--dry-run"]):
                self.assertFalse(compare_main())
            self.assertEqual(report.call_args.args[2]["summary"]["responses"], 1)
            with patch("sys.argv", ["compare.py", "--op", "funds"]), patch("compare.fetch", side_effect=OSError("offline")):
                self.assertTrue(compare_main())

    def test_sourced_signoff_requires_live_target(self):
        record = json.loads((ROOT / "parity/frozen/values/1200137.json").read_text())
        actual = {"valuesAsOfDate": "2026-06-30", "totalDepositITD": 46100,
                  "accountValues": {"endingAccountValue": 51250, "surrenderValue": 49750}}
        def withdrawal(fields):
            return next(field for field in fields if field["field"] == "WDR_TD")
        missing = withdrawal(evaluate(record, self.data, actual, 200))
        self.assertEqual(missing["result"], "fail")
        self.assertIn("accountValues.totalNetWithdrawalSinceIssue", missing["error"])
        with patch("compare.records", return_value=[record]), patch("compare.fetch", return_value=(200, actual)), patch(
                "compare.write_report") as report, patch("sys.argv", ["compare.py", "--op", "values"]):
            self.assertTrue(compare_main())
            self.assertEqual(report.call_args.args[2]["summary"]["responsesFailed"], 1)
        self.assertEqual(withdrawal(evaluate(record, self.data, dry=True))["result"], "sign-off")
        actual["accountValues"]["totalNetWithdrawalSinceIssue"] = 50
        self.assertEqual(withdrawal(evaluate(record, self.data, actual, 200))["result"], "sign-off")

    def test_sourced_signoff_array_presence_respects_paging(self):
        record = self.fund_record()
        actual = {"startIndex": 1, "itemsCount": 1, "totalItemsCount": 2,
                  "funds": [{"fundId": "F2", "fundName": "Fund 2", "fundPrice": 2.5, "totalFundValue": 12.34}]}
        fields = evaluate(record, self.data, actual, 200, start=1, limit=1)
        units = next(field for field in fields if field["field"] == "FUND_UNITS_NN")
        self.assertEqual(units["result"], "fail")
        self.assertIn("funds[0].fundSegments[0].numberOfUnits", units["error"])

    def test_required_inventory(self):
        spec = yaml.safe_load((ROOT / "vendor/iri-policy-inquiry-v1.1.5/PolicyInquiry_v1.1.5.yml").read_text())
        def visit(schema, prefix=""):
            if "$ref" in schema:
                schema = spec["components"]["schemas"][schema["$ref"].split("/")[-1]]
            for condition in schema.get("allOf", []):
                for name in condition.get("then", {}).get("required", []):
                    yield prefix + name
            for name, child in schema.get("properties", {}).items():
                path = prefix + name
                if name in schema.get("required", []):
                    yield path
                yield from visit(child, path + ".")
                if "items" in child:
                    yield from visit(child["items"], path + "[].")
        for op, name in [("summary", "PolicySummary"), ("values", "PolicyValue"), ("funds", "PolicyFunds")]:
            paths = {row["iri"] for row in self.data["rows"] if row["operation"] == op}
            self.assertFalse(set(visit(spec["components"]["schemas"][name])) - paths)


class SchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = yaml.safe_load((ROOT / "vendor/iri-policy-inquiry-v1.1.5/PolicyInquiry_v1.1.5.yml").read_text())

    def test_success_required_nested_and_format(self):
        values = validator(self.spec, "values", 200)
        self.assertFalse(list(values.iter_errors({"valuesAsOfDate": "2024-01-01", "accountValues": {"endingAccountValue": 12.34}})))
        self.assertTrue(list(values.iter_errors({"valuesAsOfDate": "not-a-date", "accountValues": {}})))
        funds = validator(self.spec, "funds", 200)
        self.assertFalse(list(funds.iter_errors({"funds": []})))
        self.assertTrue(list(funds.iter_errors({"funds": [{"fundId": "F1"}]})))
        self.assertTrue(list(validator(self.spec, "summary", 200).iter_errors({})))

    def test_error_ref_and_bad_status(self):
        for status in (400, 404, 503):
            check = validator(self.spec, "summary", status)
            self.assertFalse(list(check.iter_errors({"code": "Inquiry.Request.NotFound", "message": "No policy"})))
            self.assertTrue(list(check.iter_errors({"code": "bad code"})))
        with self.assertRaisesRegex(ValueError, "Undocumented"):
            validator(self.spec, "summary", 299)

    def test_schema_main_includes_404_and_fails_transport(self):
        record = {"contract": "42"}
        good = (200, {"valuesAsOfDate": "2024-01-01", "accountValues": {"endingAccountValue": 0}})
        missing = (404, {"code": "Inquiry.Request.NotFound", "message": "No policy"})
        with patch("schema_check.records", return_value=[record]), patch("schema_check.write_report") as report:
            with patch("sys.argv", ["schema_check.py", "--op", "values"]), patch("schema_check.fetch", side_effect=[good, missing]):
                self.assertFalse(schema_main())
            self.assertEqual(report.call_args.args[2]["summary"]["responses"], 2)
            with patch("sys.argv", ["schema_check.py", "--op", "values"]), patch("schema_check.fetch", side_effect=OSError("offline")):
                self.assertTrue(schema_main())


if __name__ == "__main__":
    unittest.main()
