"""Extract literal SQL without executing notebook cells."""
import ast
from pathlib import Path

import nbformat

NOTEBOOK = Path(__file__).resolve().parents[1] / "finance_analysis.ipynb"


def extract_queries(path=NOTEBOOK):
    notebook = nbformat.read(path, as_version=4)
    nbformat.validate(notebook)
    queries = {}
    for cell in notebook.cells:
        if "warehouse-query" not in cell.metadata.get("tags", []):
            continue
        tree = ast.parse(cell.source)
        assignments = [
            node for node in tree.body
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id.endswith("_sql")
        ]
        if len(assignments) != 1:
            raise ValueError("each warehouse-query cell must declare one literal SQL variable")
        assignment = assignments[0]
        sql = ast.literal_eval(assignment.value)
        name = assignment.targets[0].id.removesuffix("_sql")
        if not isinstance(sql, str) or not sql.strip() or name in queries:
            raise ValueError("query names must be unique with nonempty SQL")
        queries[name] = sql
    if not queries:
        raise ValueError("no warehouse-query cells")
    return queries
