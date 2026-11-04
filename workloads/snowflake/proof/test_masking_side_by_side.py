import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest

SPEC = importlib.util.spec_from_file_location("masking_proof", Path(__file__).with_name("masking_side_by_side.py"))
proof = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(proof)


@pytest.mark.parametrize("secondary_none", [False, True])
@pytest.mark.parametrize("outcome", ["rows", "empty", "denied"])
def test_run_case(monkeypatch, capsys, secondary_none, outcome):
    class ProgrammingError(Exception):
        pass

    errors = ModuleType("snowflake.connector.errors")
    errors.ProgrammingError = ProgrammingError
    monkeypatch.setitem(sys.modules, "snowflake.connector.errors", errors)
    con = MagicMock()
    cur = con.cursor.return_value
    cur.fetchone.return_value = (proof.ROLES[0], '{"value":"ALL"}')
    cur.fetchall.return_value = [] if outcome == "empty" else [proof.SEED[0]]
    cur.sfqid = "query-123"
    if outcome == "denied":
        def execute(sql):
            if sql == proof.QUERY:
                raise ProgrammingError("insufficient privileges")

        cur.execute.side_effect = execute
    monkeypatch.setattr(proof, "_connect", lambda: con)

    proof._run_case(proof.ROLES[0], secondary_none)

    output = capsys.readouterr().out
    assert "CURRENT_ROLE: " + proof.ROLES[0] in output
    assert 'CURRENT_SECONDARY_ROLES: {"value":"ALL"}' in output
    assert "query id: query-123" in output
    expected = {"rows": "ada@example.com", "empty": "(no rows)", "denied": "ERROR: insufficient privileges"}
    assert expected[outcome] in output
    statements = [call.args[0] for call in cur.execute.call_args_list]
    assert ("USE SECONDARY ROLES NONE" in statements) == secondary_none
    assert statements[0] == f"USE ROLE {proof.ROLES[0]}"
    con.close.assert_called_once()
