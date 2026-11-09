#!/usr/bin/env python3
"""Run a set of XSLT maps over input corpora with Saxon and write or check golden outputs.

Manifest (YAML):

    base: .                       # paths below are relative to this
    maps:
      - name: Fnol_to_CanonicalClaim
        xslt: Maps/Fnol_to_CanonicalClaim.xslt
        inputs: corpus/inputs/fnol      # directory of *.xml, or a glob
        golden: corpus/golden/fnol-canonical
        suffix: .xml                    # output file extension (default .xml)
        params: {CarrierCode: TMU, Count: 2, Strict: true}   # optional stylesheet parameters;
                                        # YAML booleans, integers and floats bind as xs:boolean,
                                        # xs:integer and xs:double, everything else as xs:string

`write` (re)generates the golden files; `check` transforms every input and compares the
result byte for byte with the stored golden, printing one row per message and a total.
Exit code 1 on any mismatch or missing golden so CI can gate on it.
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
import tempfile
from dataclasses import dataclass

import yaml
from saxonche import PySaxonProcessor


@dataclass
class MapSpec:
    name: str
    xslt: str
    inputs: str
    golden: str
    suffix: str = ".xml"
    params: dict | None = None


def load_manifest(path: str) -> tuple[str, list[MapSpec]]:
    with open(path, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    base = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(path)), doc.get("base", ".")))
    maps = [MapSpec(**m) for m in doc["maps"]]
    return base, maps


def list_inputs(base: str, spec: MapSpec) -> list[str]:
    pattern = os.path.join(base, spec.inputs)
    if os.path.isdir(pattern):
        pattern = os.path.join(pattern, "*.xml")
    return sorted(glob.glob(pattern))


def xdm_value(proc: PySaxonProcessor, value):
    if isinstance(value, bool):
        return proc.make_boolean_value(value)
    if isinstance(value, int):
        return proc.make_integer_value(value)
    if isinstance(value, float):
        return proc.make_double_value(value)
    return proc.make_string_value(str(value))


def transform(proc: PySaxonProcessor, xslt_path: str, input_path: str, params: dict | None) -> bytes:
    """Return the serializer's own bytes, so the stylesheet's encoding and declaration are preserved."""
    xslt = proc.new_xslt30_processor()
    executable = xslt.compile_stylesheet(stylesheet_file=xslt_path)
    if executable is None:
        raise RuntimeError(f"stylesheet failed to compile: {xslt_path}: {xslt.error_message}")
    for key, value in (params or {}).items():
        executable.set_parameter(key, xdm_value(proc, value))
    with tempfile.TemporaryDirectory() as tmp:
        out_path = os.path.join(tmp, "out.xml")
        executable.transform_to_file(source_file=input_path, output_file=out_path)
        if executable.exception_occurred or not os.path.exists(out_path):
            raise RuntimeError(f"transform failed for {input_path}: {executable.error_message}")
        with open(out_path, "rb") as fh:
            return fh.read()


def golden_path(base: str, spec: MapSpec, input_path: str) -> str:
    stem = os.path.splitext(os.path.basename(input_path))[0]
    return os.path.join(base, spec.golden, stem + spec.suffix)


def run(manifest: str, mode: str, only: str | None) -> int:
    base, maps = load_manifest(manifest)
    failures = 0
    total = 0
    with PySaxonProcessor(license=False) as proc:
        for spec in maps:
            if only and spec.name != only:
                continue
            inputs = list_inputs(base, spec)
            if not inputs:
                print(f"{spec.name}: no inputs under {spec.inputs}")
                failures += 1
                continue
            xslt_path = os.path.join(base, spec.xslt)
            targets = [golden_path(base, spec, i) for i in inputs]
            duplicates = sorted({t for t in targets if targets.count(t) > 1})
            if duplicates:
                for t in duplicates:
                    print(f"  CLASH   {spec.name} {os.path.relpath(t, base)} (two inputs share this basename)")
                failures += len(duplicates)
                continue
            ok = 0
            for input_path in inputs:
                total += 1
                out = transform(proc, xslt_path, input_path, spec.params)
                target = golden_path(base, spec, input_path)
                if mode == "write":
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    with open(target, "wb") as fh:
                        fh.write(out)
                    ok += 1
                    continue
                if not os.path.exists(target):
                    print(f"  MISSING {spec.name} {os.path.basename(input_path)}")
                    failures += 1
                    continue
                with open(target, "rb") as fh:
                    expected = fh.read()
                if expected == out:
                    ok += 1
                else:
                    failures += 1
                    print(f"  DIFF    {spec.name} {os.path.basename(input_path)}")
            verb = "written" if mode == "write" else "match"
            print(f"{spec.name}: {ok}/{len(inputs)} {verb}")
    print(f"total messages {total}, failures {failures}")
    return 1 if failures else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", choices=["write", "check"])
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--only", help="run a single map by name")
    args = parser.parse_args()
    sys.exit(run(args.manifest, args.mode, args.only))


if __name__ == "__main__":
    main()
