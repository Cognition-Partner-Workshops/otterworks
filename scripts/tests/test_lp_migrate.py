import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import Mock, patch


SPEC = importlib.util.spec_from_file_location("lp_migrate", Path(__file__).resolve().parents[1] / "lp-migrate.py")
lp = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lp)
ANN = "announcements.announcement"
PREF = "user_preferences.user_preference"
FDB = "feedback.feedback"


class MemoryDatabase:
    page_size = 2

    def __init__(self, rows=None):
        self.rows = {table: list((rows or {}).get(table, [])) for table in lp.TABLES}
        self.sequences = {ANN: 1, FDB: 1}
        self.statements = []

    def execute(self, sql, parameters=None):
        self.statements.append(sql)
        if sql.startswith("TRUNCATE"):
            self.rows = {table: [] for table in lp.TABLES}
            return []
        if sql.startswith("ALTER SEQUENCE"):
            table = sql.split()[2][:-7]
            self.sequences[table] = int(sql.split()[-1])
            return []
        if "FROM pg_sequence" in sql:
            return [(1,)]
        table = next(table for table in lp.TABLES if table in sql)
        if "last_value" in sql:
            return [(self.sequences[table], False)]
        if "EXISTS" in sql:
            return [(bool(self.rows[table]),)]
        if "count(*)" in sql:
            return [(len(self.rows[table]),)]
        rows = sorted(self.rows[table], key=lambda row: row[0])
        if parameters:
            rows = [row for row in rows if row[0] > parameters["cursor"]]
        return [(json.dumps(row),) for row in rows[:self.page_size]]

    def insert(self, table, rows):
        self.rows[table].extend(rows)


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.print_patch = patch("builtins.print")
        self.print_patch.start()
        self.addCleanup(self.print_patch.stop)

    def test_checksum_order_independent_and_duplicate_sensitive(self):
        a, b, c = lp.Checksum(), lp.Checksum(), lp.Checksum()
        rows = [[1, "quote\" newline\n café 😀", "2020-01-01 01:02:03.123456", False, "x"], [7, "", None]]
        for row in rows:
            a.add(row)
        for row in reversed(rows):
            b.add(row)
        for row in rows + rows:
            c.add(row)
        self.assertEqual(a.digest(), b.digest())
        self.assertNotEqual(a.digest(), c.digest())
        rows[0][-1] = "changed"
        d = lp.Checksum()
        for row in rows:
            d.add(row)
        self.assertNotEqual(a.digest(), d.digest())

    def test_empty_checksum_and_sequence(self):
        self.assertEqual(lp.Checksum().next_id(), 1)
        self.assertEqual(lp.Checksum().digest(), lp.Checksum().digest())

    def test_migrate_empty(self):
        target = MemoryDatabase()
        lp.migrate(MemoryDatabase(), target)
        self.assertEqual(target.sequences, {ANN: 1, FDB: 1})

    def test_migrate_preserves_values_and_gapped_ids(self):
        rows = {
            ANN: [[12, "x" * 4000, "2020-03-04 01:02:03.123456", False, "t" * 200],
                  [1, "quotes '\" and\n☃", "2000-01-01 00:00:00", True, ""],
                  [5, "third", "infinity", False, "unicode😀"]],
            PREF: [["ü" * 100, False, "l" * 20, "t" * 20]],
            FDB: [[42, "2022-02-03 12:23:45.000001", "m" * 2000, 5, "u" * 100]],
        }
        source, target = MemoryDatabase(rows), MemoryDatabase()
        lp.migrate(source, target)
        for table in rows:
            self.assertEqual(sorted(source.rows[table]), sorted(target.rows[table]))
        self.assertEqual(target.sequences, {ANN: 13, FDB: 43})

    def test_refuse_nonempty_before_copy(self):
        target = MemoryDatabase({PREF: [["existing", True, "en", "dark"]]})
        with self.assertRaisesRegex(lp.MigrationError, "non-empty"):
            lp.migrate(MemoryDatabase(), target)
        self.assertEqual(len(target.rows[PREF]), 1)

    def test_explicit_truncate(self):
        target = MemoryDatabase({PREF: [["existing", True, "en", "dark"]]})
        lp.migrate(MemoryDatabase(), target, truncate=True)
        self.assertFalse(target.rows[PREF])

    def test_dry_run_changes_neither_rows_nor_sequences(self):
        target = MemoryDatabase({PREF: [["existing", True, "en", "dark"]]})
        lp.migrate(MemoryDatabase(), target, truncate=True, dry_run=True)
        self.assertEqual(len(target.rows[PREF]), 1)
        self.assertFalse(any(sql.startswith(("TRUNCATE", "ALTER", "INSERT")) for sql in target.statements))

    def test_verification_detects_count_content_and_sequence_errors(self):
        source = MemoryDatabase({PREF: [["u", True, "en", "light"]]})
        for rows, sequence in [({}, 1), ({PREF: [["u", False, "en", "light"]]}, 1),
                               ({PREF: source.rows[PREF]}, 2)]:
            with self.subTest(rows=rows, sequence=sequence):
                target = MemoryDatabase(rows)
                target.sequences[ANN] = sequence
                with self.assertRaisesRegex(lp.MigrationError, "Verification FAILED"):
                    lp.verify(source, target)

    def test_source_sequence_gaps_are_not_mismatches(self):
        source, target = MemoryDatabase(), MemoryDatabase()
        source.sequences[ANN] = 100
        lp.verify(source, target)
        self.assertFalse(any("nextval" in s for s in target.statements))

    def test_next_sequence_handles_called_flag_and_increment(self):
        database = Mock()
        database.execute.side_effect = [[(12, True)], [(1,)]]
        self.assertEqual(lp.next_sequence(database, ANN), 13)
        database.execute.side_effect = [[(12, False)], [(1,)]]
        self.assertEqual(lp.next_sequence(database, ANN), 12)
        self.assertEqual(lp.next_sequence(database, PREF), "-")

    def test_statements_use_parameters_and_exact_timestamp_cast(self):
        self.assertNotIn("cursor", lp.select_sql(ANN, None, 25))
        self.assertIn("WHERE id > :cursor", lp.select_sql(ANN, 9, 25))
        self.assertIn("created_at::text", lp.select_sql(ANN, None, 25))
        self.assertIn("CAST(:p2 AS timestamp without time zone)", lp.insert_sql(ANN))
        self.assertNotIn("secret customer value", lp.insert_sql(FDB))
        with self.assertRaises(KeyError):
            lp.insert_sql("arbitrary; DROP TABLE x")

    def test_api_parameters_preserve_types(self):
        self.assertEqual(lp.api_parameters({"a": True, "b": 9223372036854775807, "c": "é'", "d": None}), [
            {"name": "a", "value": {"booleanValue": True}},
            {"name": "b", "value": {"longValue": 9223372036854775807}},
            {"name": "c", "value": {"stringValue": "é'"}},
            {"name": "d", "value": {"isNull": True}},
        ])

    def api(self):
        api = lp.DataAPI.__new__(lp.DataAPI)
        api.config = {"resourceArn": "cluster", "secretArn": "secret", "database": "db"}
        api.transaction = "tx"
        return api

    def test_api_batch_insert_has_no_sql_interpolation(self):
        api = self.api()
        api.call = Mock()
        rows = [[1, "value ';--", "2020-01-01 00:00:00.123456", False, "title"]]
        api.insert(ANN, rows)
        operation = api.call.call_args.args[0]
        payload = api.call.call_args.kwargs
        self.assertEqual(operation, "batch-execute-statement")
        self.assertEqual(len(payload["parameterSets"]), 1)
        self.assertNotIn(rows[0][1], payload["sql"])
        self.assertEqual(payload["parameterSets"][0][2]["value"]["stringValue"], rows[0][2])

    @patch.object(lp.subprocess, "run")
    def test_api_request_uses_stdin_transaction_and_finish_shape(self, process):
        process.return_value = subprocess.CompletedProcess([], 0, '{"records": [[{"booleanValue": false}]]}', "")
        api = self.api()
        self.assertEqual(api.execute("SELECT false"), [(False,)])
        payload = json.loads(process.call_args.kwargs["input"])
        self.assertEqual(payload["transactionId"], "tx")
        self.assertEqual(payload["database"], "db")
        self.assertNotIn("cluster", process.call_args.args[0])
        api.finish(commit=True)
        payload = json.loads(process.call_args.kwargs["input"])
        self.assertNotIn("database", payload)
        self.assertEqual(payload["transactionId"], "tx")
        self.assertIsNone(api.transaction)

    @patch.object(lp.time, "sleep")
    @patch.object(lp.subprocess, "run")
    def test_api_resume_retry(self, process, sleep):
        for reason in lp.RESUMING:
            process.side_effect = [subprocess.CompletedProcess([], 1, "", reason),
                                   subprocess.CompletedProcess([], 0, "{}", "")]
            self.api().call("execute-statement", sql="SELECT 1")
        self.assertEqual(sleep.call_count, len(lp.RESUMING))

    @patch.object(lp.time, "sleep")
    @patch.object(lp.subprocess, "run")
    def test_api_retry_exhaustion(self, process, sleep):
        process.return_value = subprocess.CompletedProcess([], 1, "", "DatabaseResumingException")
        with self.assertRaisesRegex(lp.MigrationError, "30 attempts"):
            self.api().call("execute-statement", sql="SELECT 1")
        self.assertEqual(process.call_count, 30)
        self.assertEqual(sleep.call_count, 29)

    @patch.object(lp.subprocess, "run")
    def test_api_permanent_error_does_not_leak_values_or_retry(self, process):
        process.return_value = subprocess.CompletedProcess([], 1, "", "An error occurred (BadRequestException): secret row")
        with self.assertRaisesRegex(lp.MigrationError, "BadRequestException") as error:
            self.api().call("execute-statement", sql="SELECT :secret", parameters=[])
        self.assertNotIn("secret row", str(error.exception))
        self.assertEqual(process.call_count, 1)

    @patch.object(lp, "DataAPI")
    @patch.object(lp, "Postgres")
    def test_failed_copy_rolls_back_both_connections(self, postgres, api):
        source, target = Mock(), Mock()
        postgres.side_effect = [source, target]
        source.execute.return_value = [("source",)]
        target.execute.return_value = [("target",)]
        args = Mock(source_url="source", target_url="target", command="migrate", truncate=False, dry_run=False)
        with patch.object(lp, "migrate", side_effect=lp.MigrationError("failed")):
            with self.assertRaises(lp.MigrationError):
                lp.run(args)
        source.finish.assert_called_once_with()
        target.finish.assert_called_once_with()
        api.assert_not_called()

    @patch.object(lp, "Postgres")
    def test_same_database_refused(self, postgres):
        source, target = Mock(), Mock()
        postgres.side_effect = [source, target]
        source.execute.return_value = target.execute.return_value = [("same", "host", 5432)]
        args = Mock(source_url="source", target_url="target")
        with self.assertRaisesRegex(lp.MigrationError, "different databases"):
            lp.run(args)

    @patch.object(lp, "Postgres")
    def test_copy_commits_only_after_verification(self, postgres):
        source, target = Mock(), Mock()
        postgres.side_effect = [source, target]
        source.execute.return_value = [("source",)]
        target.execute.return_value = [("target",)]
        args = Mock(source_url="source", target_url="target", command="migrate", truncate=False, dry_run=False)
        with patch.object(lp, "migrate") as migrate:
            lp.run(args)
            migrate.assert_called_once_with(source, target, False, False)
        target.finish.assert_called_once_with(commit=True)
        source.finish.assert_called_once_with()

    @patch.object(lp, "Postgres")
    def test_verify_and_dry_run_do_not_commit(self, postgres):
        for command, dry_run in [("verify", False), ("migrate", True)]:
            with self.subTest(command=command):
                source, target = Mock(), Mock()
                postgres.side_effect = [source, target]
                source.execute.return_value = [("source",)]
                target.execute.return_value = [("target",)]
                args = Mock(source_url="source", target_url="target", command=command, truncate=False, dry_run=dry_run)
                with patch.object(lp, "migrate"), patch.object(lp, "verify"):
                    lp.run(args)
                target.finish.assert_called_once_with(commit=False)

    @patch.object(lp.DataAPI, "call")
    def test_api_begin_and_rollback_on_setup_error(self, call):
        call.side_effect = [{"transactionId": "tx"}, lp.MigrationError("setup failed"), {}]
        with self.assertRaisesRegex(lp.MigrationError, "setup failed"):
            lp.DataAPI("cluster", "secret", "db")
        self.assertEqual(call.call_args.args[0], "rollback-transaction")


if __name__ == "__main__":
    unittest.main()
