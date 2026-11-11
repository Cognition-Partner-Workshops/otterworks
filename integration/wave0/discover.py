"""Validate package-owned replay selections and separately locked fault definitions."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import yaml

MODULES = {"customer-alerts", "fees-billing", "payments", "account-events",
           "statements-documents"}
STATUSES = {"matched-required", "amber", "held"}
FAULTS = {"broker-kill", "consumer-restart", "poison", "ordering"}
NAME = re.compile(r"[a-z][a-z0-9-]*")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def mapping(path):
    value = yaml.safe_load(path.read_text())
    require(isinstance(value, dict), f"{path}: expected mapping")
    return value


def contained(base, relative):
    require(isinstance(relative, str), "path must be a string")
    require(not Path(relative).is_absolute() and ".." not in Path(relative).parts,
            "path must be package-relative without traversal")
    path = (base / relative).resolve()
    require(path.is_relative_to(base.resolve()), "path escapes package")
    require(path.is_file(), f"missing file: {path}")
    return path


def validate_faults(module_dir, package, spec, flows, corpus):
    require(isinstance(spec, dict) and set(spec) == {"definitions", "lock"},
            "faults requires definitions and lock")
    base = module_dir / "src/test/resources/packages" / package / "faults"
    require(base.resolve().is_relative_to(module_dir.resolve()), "fault directory escapes module")
    definitions = contained(base, spec["definitions"])
    lock = contained(base, spec["lock"])
    require(definitions != lock, "lock cannot lock itself")
    hashes = json.loads(lock.read_text())
    require(isinstance(hashes, dict) and set(hashes) == {spec["definitions"]},
            "lock must contain exactly the definitions filename")
    require(hashes[spec["definitions"]] == hashlib.sha256(definitions.read_bytes()).hexdigest(),
            "fault definition sha256 mismatch")
    data = mapping(definitions)
    require(set(data) == {"version", "flows"} and data["version"] == 1,
            "invalid fault definitions schema")
    require(isinstance(data["flows"], dict), "fault flows must be a mapping")
    require(set(data["flows"]) <= set(flows), "fault references unselected flow")
    for flow, definition in data["flows"].items():
        require(isinstance(definition, dict)
                and set(definition) == {"source_sha256", "faults"}, "invalid fault flow schema")
        source = contained(corpus, f"{flow}/flow.json")
        require(definition["source_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest(),
                "frozen source sha256 mismatch")
        tests = definition["faults"]
        require(isinstance(tests, dict) and bool(tests) and set(tests) <= FAULTS,
                "invalid supplemental fault names")
        for name, values in tests.items():
            require(isinstance(values, dict) and bool(values), f"{name}: expected fault mapping")
    return {"definitions": str(definitions), "lock": str(lock)}


def discover(target, corpus):
    require(target.is_dir() and corpus.is_dir(), "target and corpus directories must exist")
    selected = []
    seen = set()
    for path in sorted(target.glob("*/verification/*.yaml")):
        doc = mapping(path)
        require(set(doc) == {"version", "package", "module", "flows", "faults"},
                f"{path}: invalid manifest fields")
        require(doc["version"] == 1, "unsupported manifest version")
        module, package = doc["module"], doc["package"]
        require(module in MODULES and module == path.parent.parent.name, "module/path mismatch")
        require(isinstance(package, str) and NAME.fullmatch(package) is not None
                and package == path.stem, "package/path mismatch")
        require(isinstance(doc["flows"], list) and bool(doc["flows"]), "flows must be nonempty")
        replay, held, ids = [], [], []
        for flow in doc["flows"]:
            require(isinstance(flow, dict) and set(flow) == {"id", "status", "evidence"},
                    "flow requires id, status and evidence")
            fid = flow["id"]
            require(isinstance(fid, str) and fid.startswith(module + ".")
                    and NAME.fullmatch(fid[len(module) + 1:]) is not None, "invalid flow id")
            require(fid not in seen, "duplicate flow")
            seen.add(fid)
            require((corpus / fid / "flow.json").is_file(), "unknown frozen flow")
            require(flow["status"] in STATUSES, "invalid flow status")
            require(isinstance(flow["evidence"], list) and bool(flow["evidence"])
                    and all(isinstance(e, str) and e.strip() for e in flow["evidence"]),
                    "evidence must contain nonempty strings")
            ids.append(fid)
            (held if flow["status"] == "held" else replay).append(fid)
        faults = validate_faults(path.parent.parent, package, doc["faults"], ids, corpus)
        selected.append({"package": package, "module": module, "flows": replay,
                         "held": held, "faults": faults})
    return selected


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, default=Path("integration/target"))
    parser.add_argument("--corpus", type=Path, default=Path("integration/corpus"))
    args = parser.parse_args(argv)
    try:
        packages = discover(args.target, args.corpus)
    except (ValueError, OSError, yaml.YAMLError, TypeError) as exc:
        print(f"discovery failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"include": packages}, sort_keys=True))
    if not packages:
        print("no packages selected", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
