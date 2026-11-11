import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from run import HERE, ORDER, PARAMETERS, Runner, statements
from string import Template


class RunnerTests(unittest.TestCase):
    def test_host_requires_https(self):
        for host in ("http://example.invalid", "HTTP://example.invalid", "ftp://example.invalid", "https://example.invalid", "example.invalid"):
            with self.subTest(host=host), tempfile.TemporaryDirectory() as directory, patch.dict("os.environ", {"DATABRICKS_HOST": host}):
                if host in ("https://example.invalid", "example.invalid"):
                    self.assertEqual(Runner("parity", Path(directory), Path(directory) / "ledger").host, "https://example.invalid")
                else:
                    with self.assertRaisesRegex(ValueError, "must use https"):
                        Runner("parity", Path(directory), Path(directory) / "ledger")

    @patch.dict("os.environ", {"DATABRICKS_HOST": "https://example.invalid"})
    def test_parity_mismatch_exits_with_error(self):
        for counts, differences in ((["1", "1"], []), (["1", "2"], []), (["1", "1"], [["extra"]]), (["0", "0"], [])):
            with self.subTest(counts=counts, differences=differences), tempfile.TemporaryDirectory() as directory:
                runner = Runner("parity", Path(directory), Path(directory) / "ledger.tsv")
                def file(path, **kwargs):
                    data = ([["left", counts[0], None], ["right", counts[1], None]]
                            if path == "parity/compare.sql" else differences)
                    return [{"statement_id": "id", "result": {"data_array": data}}]
                with patch("run.ORDER", ["PAYMENT"]), patch.object(runner, "file", side_effect=file), patch.object(
                        runner, "query", return_value={"result": {"data_array": [["id", "int"]]}}):
                    if counts[0] != counts[1] or differences:
                        with self.assertRaisesRegex(ValueError, "Business parity failed"):
                            runner.parity(1)
                    else:
                        runner.parity(1)

    def test_templates(self):
        for path in [HERE / "00_ddl.sql", *(HERE / ("m_SFX_" + name + ".sql") for name in ORDER)]:
            rendered = Template(path.read_text()).substitute(**PARAMETERS, STEP="convert-run1")
            for statement in statements(rendered):
                self.assertTrue(statement.startswith("/* run=dbx-d1111 act=scale step=convert-run1 consumer=m_SFX_"))
                self.assertNotIn("${", statement)
                self.assertNotRegex(statement, r"cpw\.dbx_d1111_after\.billing__(?!sfx_)")
            if path.name == "00_ddl.sql":
                self.assertEqual(len(statements(rendered)), 8)
                self.assertEqual(rendered.count("COMMENT 'run_token=dbx-d1111 expires=2026-11-24'"), 8)

    def test_empty_input(self):
        self.assertEqual(statements(" ; \n ;"), [])

    @patch.dict("os.environ", {"DATABRICKS_HOST": "https://example.invalid", "DATABRICKS_WAREHOUSE_ID": "test"})
    def test_success_and_failure_evidence(self):
        for state in ("SUCCEEDED", "FAILED"):
            with self.subTest(state=state), tempfile.TemporaryDirectory() as directory:
                output = Path(directory)
                runner = Runner("parity", output, output / "statements.tsv")
                result = {"statement_id": "test-id", "status": {"state": state}}
                with patch.object(runner, "api", return_value=result):
                    sql = "/* run=dbx-d1111 act=scale step=parity consumer=m_SFX_PAYMENT */\nSELECT 1"
                    if state == "FAILED":
                        with self.assertRaises(RuntimeError):
                            runner.execute(sql, "test")
                    else:
                        self.assertEqual(runner.execute(sql, "test"), result)
                self.assertEqual(json.loads((output / "statements.json").read_text())[0]["result"], result)
                with (output / "statements.tsv").open() as f:
                    self.assertEqual(list(csv.DictReader(f, delimiter="\t"))[0]["state"], state)

    @patch.dict("os.environ", {"DATABRICKS_HOST": "https://example.invalid"})
    def test_invalid_header_never_submits(self):
        with tempfile.TemporaryDirectory() as directory:
            runner = Runner("parity", Path(directory), Path(directory) / "statements.tsv")
            with patch.object(runner, "api") as api:
                with self.assertRaises(ValueError):
                    runner.execute("SELECT 1", "bad")
                api.assert_not_called()


if __name__ == "__main__":
    unittest.main()
