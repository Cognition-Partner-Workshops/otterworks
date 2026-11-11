import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "jobs/py"))
from common.runtime import refresh_columns, save_jdbc_refresh, save_partition

spec = importlib.util.spec_from_file_location("template_submit", ROOT / "template/submit.py")
submit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(submit)


def target_rows(connection, names):
    rows = connection.prepareStatement.return_value.executeQuery.return_value
    rows.next.side_effect = [True] * len(names) + [False]
    rows.getString.side_effect = names


class TemplateTest(unittest.TestCase):
    def test_submission(self):
        args = submit.arguments("file_object_binary_extract")
        self.assertIn("--properties-file", args)
        self.assertTrue(args[-1].endswith("file_object_binary_extract.py"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = root / "jobs/registry"
            registry.mkdir(parents=True)
            (registry / "scala_example.yaml").write_text(json.dumps({
                "status": "template", "language": "scala", "profile": "small", "class": "sfx.Example",
            }))
            with patch.object(submit, "ROOT", root):
                args = submit.arguments("scala_example")
        self.assertEqual(args[args.index("--class") + 1], "sfx.Example")
        self.assertFalse(any("password" in arg.lower() for arg in args))

    def test_inactive_submission(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = root / "jobs/registry"
            registry.mkdir(parents=True)
            for status in ("snowflake", "retired"):
                (registry / "inactive.yaml").write_text(json.dumps({"status": status}))
                with patch.object(submit, "ROOT", root), self.assertRaises(ValueError):
                    submit.arguments("inactive")

    def test_invalid_submission(self):
        for job in ("", "../unknown", "missing"):
            with self.assertRaises((ValueError, FileNotFoundError)):
                submit.arguments(job)

    def test_jdbc_transaction(self):
        for empty in (False, True):
            frame = MagicMock()
            frame.columns = ["value"]
            frame.isEmpty.return_value = empty
            connection = frame.sparkSession.sparkContext._jvm.java.sql.DriverManager.getConnection.return_value
            target_rows(connection, ["value"])
            with patch.dict("os.environ", {"TD_JDBC_PASSWORD": "test-only"}):
                save_jdbc_refresh(frame, "test.result")
            connection.commit.assert_called_once()
            connection.rollback.assert_not_called()
            connection.close.assert_called_once()
            sql = [call.args[0] for call in connection.createStatement.return_value.executeUpdate.call_args_list]
            self.assertEqual(sql[0], "DELETE FROM test.result")
            self.assertTrue(sql[1].startswith('INSERT INTO test.result ("value") SELECT "value" FROM test._sfx_stage_'))

    def test_jdbc_existing_lowercase_target(self):
        frame = MagicMock()
        frame.columns = ["ACCOUNT_ID", "Region"]
        connection = frame.sparkSession.sparkContext._jvm.java.sql.DriverManager.getConnection.return_value
        target_rows(connection, ["account_id", "region"])
        with patch.dict("os.environ", {"TD_JDBC_PASSWORD": "test-only"}):
            save_jdbc_refresh(frame, "sfx_billing.customer_account")
        connection.prepareStatement.return_value.setString.assert_called_once_with(1, "sfx_billing.customer_account")
        sql = connection.createStatement.return_value.executeUpdate.call_args_list[1].args[0]
        self.assertTrue(sql.startswith(
            'INSERT INTO sfx_billing.customer_account ("account_id", "region") SELECT "ACCOUNT_ID", "Region" FROM '
        ))

    def test_refresh_columns(self):
        self.assertEqual(refresh_columns(["ID", "Id"], ["ID", "Id"]), [("ID", "ID"), ("Id", "Id")])
        self.assertEqual(refresh_columns(["ID"], ["id", "extra"]), [("id", "ID")])
        for target in (["other"], ["id", "Id"]):
            with self.assertRaises(ValueError):
                refresh_columns(["ID"], target)

    def test_jdbc_error(self):
        frame = MagicMock()
        frame.write.format.return_value.options.return_value.option.return_value.mode.return_value.save.side_effect = RuntimeError("write failed")
        connection = frame.sparkSession.sparkContext._jvm.java.sql.DriverManager.getConnection.return_value
        with patch.dict("os.environ", {"TD_JDBC_PASSWORD": "test-only"}):
            with self.assertRaisesRegex(RuntimeError, "write failed"):
                save_jdbc_refresh(frame, "test.result")
        connection.rollback.assert_called_once()
        connection.commit.assert_not_called()
        connection.close.assert_called_once()
        with self.assertRaises(ValueError):
            save_jdbc_refresh(frame, "bad;sql")

    def test_partition_invalid_date(self):
        with self.assertRaises(ValueError):
            save_partition(MagicMock(), "test", "result", "../bad")
