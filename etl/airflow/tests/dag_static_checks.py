"""AST checks on DAG files: explicit schedule and nothing that opens a connection at parse time."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

DAG_FACTORIES = {"DAG", "dag"}
TASK_DECORATORS = {"task"}
FORBIDDEN_ATTRS = {"get_conn", "get_connection", "get_hook", "get_records", "run"}


def _name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Call):
        node = node.func
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Attribute):
        return f"{_dotted(node.value)}.{node.attr}"
    if isinstance(node, ast.Name):
        return node.id
    return "?"


def _is_dag_function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return any(_name(d) in DAG_FACTORIES for d in node.decorator_list)


def _parse_time_children(node: ast.AST) -> Iterator[ast.AST]:
    """Yield the children of ``node`` that run while the DagBag imports the file.

    Bodies of plain and ``@task`` functions are deferred to task run time; a ``@dag`` function
    body runs at parse time, as do class bodies, decorators and default values. A plain
    module-level helper's body is followed by ``_walk_parse_time`` when parse-time code calls it.
    """
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        yield from node.decorator_list
        yield from node.args.defaults
        yield from (d for d in node.args.kw_defaults if d is not None)
        if _is_dag_function(node):
            yield from node.body
    elif not isinstance(node, ast.Lambda):
        yield from ast.iter_child_nodes(node)


def _module_helpers(tree: ast.Module) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    """Undecorated module-level functions: their bodies run at parse time when called there."""
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and not node.decorator_list
    }


def _walk_parse_time(tree: ast.Module) -> Iterator[ast.AST]:
    """Walk parse-time code, following calls into this module's own helper functions."""
    helpers = _module_helpers(tree)
    followed: set[str] = set()
    stack: list[ast.AST] = [tree]
    while stack:
        node = stack.pop()
        yield node
        stack.extend(_parse_time_children(node))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            helper = helpers.get(node.func.id)
            if helper is not None and helper.name not in followed:
                followed.add(helper.name)
                stack.extend(helper.body)


def top_level_hook_calls(source: str) -> list[str]:
    """Calls that instantiate a hook or read a Connection/Variable at DAG parse time."""
    problems = []
    for node in _walk_parse_time(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        name = _name(node) or ""
        dotted = _dotted(node.func)
        if (
            name.endswith("Hook")
            or dotted.endswith("Variable.get")
            or (isinstance(node.func, ast.Attribute) and name in FORBIDDEN_ATTRS)
        ):
            problems.append((node.lineno, f"line {node.lineno}: {dotted}(...)"))
    return [msg for _, msg in sorted(problems)]


def dag_calls_without_schedule(source: str) -> list[str]:
    """``DAG(...)`` / ``@dag(...)`` calls that leave ``schedule`` to Airflow's default."""
    problems = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call) and _name(node.func) in DAG_FACTORIES:
            if "schedule" not in {k.arg for k in node.keywords}:
                problems.append((node.lineno, f"line {node.lineno}: {_dotted(node.func)}(...)"))
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            for deco in node.decorator_list:
                if isinstance(deco, ast.Name | ast.Attribute) and _name(deco) in DAG_FACTORIES:
                    problems.append((deco.lineno, f"line {deco.lineno}: bare @{_dotted(deco)}"))
    return [f"{msg} has no schedule=" for _, msg in sorted(problems)]


def dag_files(folder: Path) -> list[Path]:
    return sorted(p for p in folder.rglob("*.py") if not p.name.startswith("_"))
