#!/usr/bin/env python3
"""Check Prometheus alert runbook annotations and repository-local link targets."""

from pathlib import Path
import sys
from urllib.parse import unquote, urlparse

import yaml

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "https://github.com/Cognition-Partner-Workshops/otterworks/blob/main/"


def check(paths):
    errors = []
    count = 0
    for path in paths:
        data = yaml.safe_load(path.read_text()) or {}
        for group in data.get("groups", []):
            for rule in group.get("rules", []):
                if "alert" not in rule:
                    continue
                count += 1
                link = rule.get("annotations", {}).get("runbook_url", "")
                if not isinstance(link, str) or not link:
                    errors.append(f"{path}: {rule['alert']} missing runbook_url")
                    continue
                parsed = urlparse(link)
                if link.startswith(PREFIX):
                    target = ROOT / unquote(link[len(PREFIX):].split("#")[0])
                    if not target.resolve().is_relative_to(ROOT) or not target.is_file():
                        errors.append(f"{path}: {rule['alert']} missing local target: {link}")
                elif parsed.scheme not in ("https", "http") or not parsed.netloc:
                    errors.append(f"{path}: {rule['alert']} invalid runbook URL: {link}")
    return count, errors


def main():
    paths = sorted((ROOT / "observability/prometheus").glob("*.yml"))
    paths += sorted((ROOT / "infrastructure/helm").glob("*/files/*.yml"))
    count, errors = check(paths)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"Runbooks OK: {count} alert definitions; repository-local targets exist")
    return 0


if __name__ == "__main__":
    sys.exit(main())
