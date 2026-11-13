import argparse
import json
import re
from pathlib import Path

import yaml


def generate(manifest, database=None, schema="PUBLIC"):
    if manifest.get("version") != 1:
        raise ValueError("Unsupported loader manifest version")
    tables = []
    for obj in manifest["objects"]:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", obj["name"]):
            raise ValueError("Invalid source identifier")
        tables.append({"name": obj["name"].lower(), "identifier": obj["name"],
                       "columns": [{"name": c["name"], "data_type": c["type"]} for c in obj["columns"]]})
    source = {"name": "frozen_input", "schema": schema, "quoting": {"identifier": True}, "tables": tables}
    if database:
        source["database"] = database
    return {"version": 2, "sources": [source]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out", default="models/sources.yml")
    parser.add_argument("--database")
    parser.add_argument("--schema", default="PUBLIC")
    args = parser.parse_args()
    document = generate(json.loads(Path(args.manifest).read_text()), args.database, args.schema)
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(document, sort_keys=False))


if __name__ == "__main__":
    main()
