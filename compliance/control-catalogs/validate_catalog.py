import argparse
import json
from pathlib import Path
import re


DEFAULT_CATALOG = Path(__file__).with_name("secure-software-controls.yaml")


def validate_catalog(catalog):
    if not isinstance(catalog, dict):
        raise ValueError("catalog must be an object")
    controls = catalog.get("controls")
    if not isinstance(controls, list) or not controls:
        raise ValueError("controls must be a non-empty list")
    seen = set()
    for control in controls:
        if not isinstance(control, dict):
            raise ValueError("each control must be an object")
        control_id = control.get("id")
        if not isinstance(control_id, str) or not re.fullmatch(r"SSC-\d\d", control_id):
            raise ValueError("control id must match SSC-\\d\\d")
        if control_id in seen:
            raise ValueError(f"duplicate control id: {control_id}")
        seen.add(control_id)
        for field in ("title", "text"):
            value = control.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{control_id}: {field} must be a non-empty string")
        for field in ("references", "evidence"):
            value = control.get(field)
            if (
                not isinstance(value, list)
                or not value
                or any(not isinstance(item, str) or not item.strip() for item in value)
            ):
                raise ValueError(f"{control_id}: {field} must be a non-empty list of strings")
    return [{"id": c["id"], "text": f'{c["title"]}: {c["text"]}'} for c in controls]


def main():
    parser = argparse.ArgumentParser(
        description="Validate a control catalog encoded as JSON-compatible YAML."
    )
    parser.add_argument("catalog", nargs="?", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--criteria-json", action="store_true")
    args = parser.parse_args()
    try:
        catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
        criteria = validate_catalog(catalog)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Invalid catalog: {exc}\n")
    if args.criteria_json:
        print(json.dumps(criteria))
    else:
        print(f"Validated {len(criteria)} controls.")


if __name__ == "__main__":
    main()
