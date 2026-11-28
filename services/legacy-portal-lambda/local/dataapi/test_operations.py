import json
import re
import unittest
from pathlib import Path

import operations as ops

PARAM = re.compile(r"(?<![:\w]):([A-Za-z_]\w*)")
LAMBDA_ROOT = Path(__file__).resolve().parents[2]
JAVA_STRING = r'"(?:[^"\\\r\n]|\\.)*"'


def s(v):
    return {"stringValue": v}


def java_sql(source, schema, inline):
    def evaluate(expression, variables):
        atom = rf"(?:{JAVA_STRING}|{'|'.join(variables)})"
        if not re.fullmatch(rf"\s*{atom}(?:\s*\+\s*{atom})*\s*", expression):
            raise AssertionError(f"Unsupported Java SQL expression: {expression!r}")
        return "".join(json.loads(part) if part.startswith('"') else variables[part]
                       for part in re.findall(atom, expression))

    tables = re.findall(r"\bthis\.table\s*=\s*([^;]+);", source)
    if len(tables) != 1:
        raise AssertionError("Expected exactly one table assignment")
    table = evaluate(tables[0], {"schema": schema})
    if inline:
        expressions = []
        for call in re.finditer(r"\bexecute\s*\(\s*", source):
            tail = source[call.end():]
            if re.match(r"String\s+sql\b|sql\s*,\s*List\.of\(\)\)", tail):
                continue
            first_arg = re.match(rf'((?:{JAVA_STRING}|[^",);])*)[,)]', tail)
            if first_arg is None:
                raise AssertionError(f"Cannot read Java execute SQL argument: {tail[:80]!r}")
            expressions.append(first_arg[1])
    else:
        expressions = re.findall(rf'\bString\s+sql\s*=\s*((?:{JAVA_STRING}|[^";])*);', source)
    return [evaluate(expression, {"table": table}) for expression in expressions]


class ResolveTest(unittest.TestCase):
    def test_every_operation_binds_exactly_its_handler_parameters(self):
        for op in ops.OPERATIONS:
            names = {spec[0] for spec in op.params}
            self.assertEqual(set(PARAM.findall(op.handler_sql)), names, op.name)
            self.assertEqual(set(re.findall(r"%\((\w+)\)s", op.sql)), names, op.name)
            self.assertNotIn(":", PARAM.sub("", op.sql.replace("::", "")), op.name)

    def test_handler_statements_are_unique(self):
        self.assertEqual(len({op.handler_sql for op in ops.OPERATIONS}), len(ops.OPERATIONS))

    def test_every_statement_resolves_and_keeps_values_separate(self):
        samples = {ops.STRING: "text with ' and %", ops.LONG: 7, ops.BOOLEAN: True}
        for op in ops.OPERATIONS:
            with self.subTest(operation=op.name):
                params = [{"name": name, "value": {kind: samples[kind]},
                           **({"typeHint": hint} if hint else {})} for name, kind, hint in op.params]
                resolved, values = ops.resolve(op.handler_sql, params)
                self.assertIs(resolved, op)
                self.assertEqual(values, {name: samples[kind] for name, kind, _ in op.params})
                self.assertNotIn(samples[ops.STRING], resolved.sql)

    def test_sql_from_java_repositories_resolves_exactly(self):
        compose = (LAMBDA_ROOT / "local/docker-compose.yml").read_text()
        schemas = dict(re.findall(r"^  fn-(\w+):\n(?:(?:^ {4,}.*)\n)*?^      DB_SCHEMA: (\w+)$",
                                  compose, re.MULTILINE))
        self.assertEqual(set(schemas), {"announcements", "preferences", "feedback"})
        operations = {op.handler_sql: op for op in ops.OPERATIONS}
        emitted = []
        for module, schema in schemas.items():
            sources = list((LAMBDA_ROOT / module / "src/main/java").rglob("DataApi*Repository.java"))
            self.assertEqual(len(sources), 1, module)
            for sql in java_sql(sources[0].read_text(), schema, inline=module == "announcements"):
                emitted.append(sql)
                with self.subTest(repository=sources[0].name, sql=sql):
                    op = operations.get(sql)
                    params = [{"name": name, "value": {"isNull": True},
                               **({"typeHint": hint} if hint else {})}
                              for name, _, hint in op.params] if op else []
                    self.assertIs(ops.resolve(sql, params)[0], op)
        self.assertCountEqual(emitted, operations.keys())

    def test_known_statement_resolves_to_static_sql(self):
        op, values = ops.resolve(
            "SELECT user_id, theme, locale, email_notifications FROM user_preferences.user_preference"
            " WHERE user_id = :u", [{"name": "u", "value": s("u1")}])
        self.assertEqual(op.name, "preferences.by-user")
        self.assertIn("%(u)s::varchar", op.sql)
        self.assertEqual(values, {"u": "u1"})

    def test_typed_and_null_values(self):
        op, values = ops.resolve(ops.OPERATIONS[1].handler_sql, [
            {"name": "id", "value": {"longValue": 7}}, {"name": "title", "value": s("t")},
            {"name": "body", "value": {"isNull": True}}, {"name": "published", "value": {"booleanValue": True}},
            {"name": "created_at", "value": s("2026-01-02 03:04:05")}])
        self.assertEqual(values, {"id": 7, "title": "t", "body": None, "published": True,
                                  "created_at": "2026-01-02 03:04:05"})

    def test_unknown_statement_fails_closed(self):
        for sql in ["", "SELECT 1", "DROP TABLE feedback.feedback",
                    ops.OPERATIONS[3].handler_sql + " ", ops.OPERATIONS[3].handler_sql.lower()]:
            with self.assertRaises(ops.OperationError, msg=sql):
                ops.resolve(sql, [])

    def test_parameter_mismatches_fail_closed(self):
        by_user = ops.OPERATIONS[5].handler_sql
        cases = [
            [],
            [{"name": "u", "value": s("a")}, {"name": "x", "value": s("b")}],
            [{"name": "u", "value": s("a")}, {"name": "u", "value": s("b")}],
            [{"name": "u", "value": {"longValue": 1}}],
            [{"name": "u", "value": {"stringValue": "a", "longValue": 1}}],
            [{"name": "u", "value": s("a"), "typeHint": "TIMESTAMP"}],
            ["u"],
        ]
        for params in cases:
            with self.assertRaises(ops.OperationError, msg=params):
                ops.resolve(by_user, params)

    def test_type_hint_is_required_where_the_handler_sends_one(self):
        insert = ops.OPERATIONS[7]
        params = [{"name": "createdAt", "value": s("2026-01-02 03:04:05.000")}, {"name": "message", "value": s("m")},
                  {"name": "rating", "value": {"longValue": 5}}, {"name": "userId", "value": s("u")}]
        with self.assertRaises(ops.OperationError):
            ops.resolve(insert.handler_sql, params)
        params[0]["typeHint"] = "TIMESTAMP"
        self.assertEqual(ops.resolve(insert.handler_sql, params)[0].name, "feedback.insert")


if __name__ == "__main__":
    unittest.main()
