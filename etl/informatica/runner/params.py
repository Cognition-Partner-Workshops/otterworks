"""Parameter files and $PM process variables."""

from __future__ import annotations

import os
import re

_SECTION = re.compile(r"^\[(?P<name>[^\]]+)\]\s*$")


def parse_param_file(path):
    """Return {section: {name: value}} preserving PowerCenter section headings."""
    sections: dict = {}
    current = None
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n").rstrip("\r")
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith(";"):
                continue
            m = _SECTION.match(stripped)
            if m:
                current = m.group("name").strip()
                sections.setdefault(current, {})
                continue
            if "=" in line and current is not None:
                k, v = line.split("=", 1)
                sections[current][k.strip()] = v.strip()
    return sections


def _match(section, folder, workflow, session):
    s = section.upper()
    if s == "GLOBAL":
        return 0
    folder, workflow = folder.upper(), workflow.upper()
    wf_key = f"{folder}.WF:{workflow}"
    if s == wf_key:
        return 1
    if session:
        session = session.upper()
        if s in (f"{wf_key}.ST:{session}", f"{folder}.ST:{session}", f"{folder}.WF:{workflow}.WT:{session}"):
            return 2
        if s.startswith(wf_key + ".") and s.endswith(".ST:" + session):
            return 2
    return None


def resolve(param_files, folder, workflow, session=None):
    """Merge the applicable sections of the given parameter files.

    Later files override earlier ones; within a file, session sections
    override workflow sections, which override [Global].
    """
    merged: dict = {}
    for path in param_files:
        if not path or not os.path.exists(path):
            continue
        layers = []
        for section, values in parse_param_file(path).items():
            rank = _match(section, folder, workflow, session)
            if rank is not None:
                layers.append((rank, values))
        for _, values in sorted(layers, key=lambda x: x[0]):
            merged.update(values)
    return merged


def expand(text, values, process_vars):
    """Substitute $$params, $Params and $PM process variables inside attribute values."""
    if not text:
        return text

    def repl(m):
        name = m.group(0)
        for table in (values, process_vars):
            for k, v in table.items():
                if k.upper() == name.upper():
                    return expand(v, values, process_vars) if "$" in v and v != name else v
        return name

    return re.sub(r"\$\$?[A-Za-z_][A-Za-z0-9_]*", repl, text)
