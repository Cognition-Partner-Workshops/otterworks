import csv
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from job import Job, TAGS, assert_parity, definition, sql_files
from run import HERE, ORDER, statements


class JobTests(unittest.TestCase):
    def test_definition_matches_worklet_and_workflow(self):
        config = definition("/Users/example/dbx-d1111/SFX_BILLING", "warehouse")
        self.assertEqual(config["tags"], TAGS)
        self.assertEqual(config["max_concurrent_runs"], 1)
        tasks = {t["task_key"]: t for t in config["tasks"]}
        dependencies = lambda key: {d["task_key"] for d in tasks[key].get("depends_on", [])}
        self.assertEqual(dependencies("s_STG_CUSTOMER_ACCOUNT"), set())
        self.assertEqual(dependencies("s_STG_INVOICE_HDR"), set())
        self.assertEqual(dependencies("s_CUSTOMER_ACCOUNT"), {"s_STG_CUSTOMER_ACCOUNT"})
        for key in ("s_INVOICE_HDR", "s_INVOICE_LINE"):
            self.assertEqual(dependencies(key), {"s_CUSTOMER_ACCOUNT", "s_STG_INVOICE_HDR"})
        self.assertEqual(dependencies("s_GL_JOURNAL_LINE"), {"s_INVOICE_HDR", "s_INVOICE_LINE"})
        self.assertEqual(tasks["dec_GL_POSTED"]["run_if"], "ALL_DONE")
        self.assertEqual(tasks["dec_GL_POSTED"]["condition_task"]["right"], "success")
        self.assertEqual(tasks["s_PAYMENT"]["depends_on"][0]["outcome"], "true")
        self.assertEqual(tasks["em_GL_POSTING_ALERT"]["depends_on"][0]["outcome"], "false")
        for task in tasks.values():
            self.assertNotIn("new_cluster", task)
            self.assertNotIn("existing_cluster_id", task)
            if "sql_task" in task:
                self.assertEqual(task["sql_task"]["warehouse_id"], "warehouse")
        xml = ET.parse(HERE.parents[2] / "informatica/repository/SFX_BILLING/wf_SFX_BILLING_DAILY.XML")
        worklet = xml.find(".//WORKLET[@NAME='wklt_SFX_BILLING_STAGE']")
        members = worklet.findall("TASKINSTANCE[@TASKTYPE='Session']")
        self.assertEqual({t.attrib["NAME"] for t in members}, {
            "s_m_SFX_STG_CUSTOMER_ACCOUNT", "s_m_SFX_CUSTOMER_ACCOUNT", "s_m_SFX_STG_INVOICE_HDR"})
        self.assertTrue(all(t.attrib["FAIL_PARENT_IF_INSTANCE_FAILS"] == "YES" for t in members))

    def test_rendered_sql(self):
        files = sql_files()
        self.assertEqual(len(files), 8)
        self.assertEqual(sum(len(statements(text)) for key, text in files.items() if key.startswith("m_SFX_")), 8)
        gl = statements(files["m_SFX_GL_JOURNAL_LINE.sql"])
        self.assertEqual(len(gl), 1)
        self.assertIn("REPLACE WHERE journal_no LIKE 'JE-20261109-%'", gl[0])
        for text in files.values():
            for sql in statements(text):
                self.assertTrue(sql.startswith("/* run=dbx-d1111 act=scale step=job-run consumer=m_SFX_"))
                self.assertNotIn("${", sql)

    def test_parity_normal_empty_and_mismatch(self):
        rows = [{"mapping": name, "reference": "corrected", "hash_rows": [["left", "1", "2"], ["right", "1", "2"]],
                 "differences": [{"rows": []}, {"rows": []}]} for name in ORDER]
        assert_parity(rows)
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            assert_parity([])
        rows[0]["differences"][0]["rows"] = [["difference"]]
        with self.assertRaisesRegex(ValueError, "Business parity failed"):
            assert_parity(rows)

    @patch.dict("os.environ", {"DATABRICKS_HOST": "https://example.invalid", "DATABRICKS_WAREHOUSE_ID": "warehouse"})
    def test_reject_non_serverless_and_duplicate_job(self):
        with tempfile.TemporaryDirectory() as directory:
            job = Job(Path(directory), Path(directory) / "ledger.tsv")
            with patch.object(job, "api", return_value={"enable_serverless_compute": False}):
                with self.assertRaisesRegex(ValueError, "not serverless"):
                    job.deploy()
            with patch.object(job, "api", side_effect=[{"enable_serverless_compute": True}, {"userName": "example"}, {"jobs": [{}]}]):
                with self.assertRaisesRegex(ValueError, "duplicate"):
                    job.deploy()

    @patch.dict("os.environ", {"DATABRICKS_HOST": "https://example.invalid"})
    def test_run_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            job = Job(Path(directory), Path(directory) / "ledger.tsv")
            job.state = {"job_id": 1, "runs": [{"run_id": 2}]}
            with patch.object(job, "api", return_value={"settings": {"tags": TAGS}}) as api:
                with self.assertRaisesRegex(ValueError, "unfinished"):
                    job.run_once()
                self.assertEqual(api.call_count, 1)

    @patch.dict("os.environ", {"DATABRICKS_HOST": "https://example.invalid"})
    def test_failed_run_still_records_statements(self):
        with tempfile.TemporaryDirectory() as directory:
            job = Job(Path(directory), Path(directory) / "ledger.tsv")
            job.state = {"job_id": 1, "runs": []}
            def fail(run):
                run["state"] = {"life_cycle_state": "TERMINATED", "result_state": "FAILED"}
            with patch.object(job, "api", side_effect=[{"settings": {"tags": TAGS}}, {"run_id": 2}]), \
                    patch.object(job, "collect", side_effect=fail), patch.object(job, "record_statements") as record:
                with self.assertRaisesRegex(RuntimeError, "Job failed"):
                    job.run_once()
                record.assert_called_once_with(job.state["runs"][0])

    @patch.dict("os.environ", {"DATABRICKS_HOST": "https://example.invalid", "DATABRICKS_WAREHOUSE_ID": "warehouse"})
    def test_statement_history_normal_empty_error_and_deduplication(self):
        sql = "/* run=dbx-d1111 act=scale step=job-run consumer=m_SFX_PAYMENT */\nSELECT 1;"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            job = Job(path, path / "ledger.tsv")
            run = {"run_id": 1, "start_time": 2, "end_time": 3}
            output = {"s_PAYMENT": {"sql_output": {"file_output": {
                "query_text": sql, "sql_statements": [{"lookup_key": "opaque"}]}}}}
            (path / "1-outputs.json").write_text(json.dumps(output))
            with patch.object(job, "api", return_value={"res": []}):
                with self.assertRaisesRegex(ValueError, "retry collect"):
                    job.record_statements(run)
            history = {"res": [{"lookup_key": "opaque", "query_id": "statement-id",
                                 "query_text": sql, "status": "FINISHED"}]}
            with patch.object(job, "api", return_value=history):
                job.record_statements(run)
                job.record_statements(run)
            with (path / "ledger.tsv").open() as f:
                rows = list(csv.DictReader(f, delimiter="\t"))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["state"], "SUCCEEDED")
            history["res"][0].update(query_id="failed-id", status="FAILED")
            with patch.object(job, "api", return_value=history):
                job.record_statements(run)
            with (path / "ledger.tsv").open() as f:
                self.assertEqual(list(csv.DictReader(f, delimiter="\t"))[-1]["state"], "FAILED")
            (path / "1-outputs.json").write_text("{}")
            with patch.object(job, "api", return_value={"res": []}):
                with self.assertRaisesRegex(ValueError, "No SQL statements"):
                    job.record_statements(run)


if __name__ == "__main__":
    unittest.main()
