"""JSON query bridge to the warehouse worktree's own Teradata Runner."""
import argparse
from datetime import date, datetime
from decimal import Decimal
import io
import json
import os
from pathlib import Path
import sys


def runtime_path():
    home = Path(os.environ["TD_EMULATOR_HOME"]) if "TD_EMULATOR_HOME" in os.environ else Path(__file__).resolve().parents[2]
    runtime = home.resolve() / "warehouse" / "teradata"
    if not (runtime / "bteq" / "runner.py").is_file():
        raise ValueError("Set TD_EMULATOR_HOME to a repository containing warehouse/teradata/bteq")
    return runtime


def runner_class():
    runtime = runtime_path()
    sys.path.insert(0, str(runtime))
    from bteq import Runner
    from sqlglot import exp, parse_one

    class CaseSensitiveRunner(Runner):
        def case_insensitive(self, tree, column):
            return False

        def translate(self, source):
            statement, after = super().translate(source)
            if not statement:
                return statement, after
            tree = parse_one(statement, read="postgres")
            types = self.resolve_types(tree)
            for column in list(tree.find_all(exp.Column)):
                if types.get(column.name.lower(), "").startswith(("character", "varchar", "text")):
                    column.replace(exp.Collate(
                        this=column.copy(), expression=exp.Identifier(this="C", quoted=True)
                    ))
            return tree.sql(dialect="postgres"), after

    return Runner, CaseSensitiveRunner


def json_value(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(f"unsupported warehouse value type: {type(value).__name__}")


def execute(sql, target="teradata-emulator"):
    normal, sensitive = runner_class()
    if target not in {"teradata-emulator", "snowflake-semantics"}:
        raise ValueError(f"unsupported live bridge target: {target}")
    output = io.StringIO()
    cls = sensitive if target == "snowflake-semantics" else normal
    with cls(output=output) as runner:
        runner.execute(sql)
        if runner.errorcode:
            raise RuntimeError(f"warehouse query failed ({runner.sqlstate}): {output.getvalue().strip()}")
        return {"columns": [name.upper() for name in runner.headers], "rows": [list(row) for row in runner.rows]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sql-file", type=Path)
    parser.add_argument("--target", choices=["teradata-emulator", "snowflake-semantics"],
                        default=os.getenv("WAREHOUSE_CONTRACT_TARGET", "teradata-emulator"))
    parser.add_argument("--query", help="optional fixture query name")
    parser.add_argument("--record", type=Path, help="write this exact live result as recorded JSON")
    args = parser.parse_args()
    try:
        sql = args.sql_file.read_text() if args.sql_file else sys.stdin.read()
        if not sql.strip():
            raise ValueError("SQL input is empty")
        result = execute(sql, args.target)
        if args.query:
            result = {"query": args.query, **result}
        payload = json.dumps(result, default=json_value, indent=2) + "\n"
        if args.record:
            if args.target != "teradata-emulator":
                raise ValueError("--record requires teradata-emulator")
            args.record.parent.mkdir(parents=True, exist_ok=True)
            args.record.write_text(payload)
        sys.stdout.write(payload)
        return 0
    except Exception as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
