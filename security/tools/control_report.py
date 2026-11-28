import json
from pathlib import Path

import yaml


def load(path):
    return yaml.safe_load(Path(path).read_text())


def markdown_table(rows, columns):
    def cell(value):
        return str(value).replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>")

    def line(values):
        return "| " + " | ".join(cell(value) for value in values) + " |"

    return "\n".join([
        line(label for _, label in columns),
        line("---" for _ in columns),
        *(line(row[key] for key, _ in columns) for row in rows),
    ])


def report(output, title, rows, columns, totals):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.with_name(output.name + ".json").write_text(json.dumps({"summary": totals, "checks": rows}, indent=2) + "\n")
    counts = ", ".join(f"{key}: {value}" for key, value in totals.items())
    output.with_name(output.name + ".md").write_text(f"# {title}\n\n{counts}\n\n{markdown_table(rows, columns)}\n")


def assertion_report(output, title, rows, columns):
    passed = sum(row["passed"] for row in rows)
    report(output, title, rows, columns, {"passed": passed, "failed": len(rows) - passed})
    return int(passed != len(rows))
