#!/usr/bin/env python3
"""CarrierSAST export generator.

Extracts a path list from one git commit, runs Semgrep over it with the
registry rulesets for Java, XML and shell plus the carrier's custom rules,
and writes a SARIF 2.1.0 log stamped as a CarrierSAST run: tool name, run id,
the commit scanned and the paths covered.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import jsonschema

TOOL_NAME = "CarrierSAST"
TOOL_VERSION = "1.0.0"
TOOL_ORGANIZATION = "Carrier Application Security"

HERE = Path(__file__).resolve().parent
CUSTOM_RULES = HERE / "rules" / "carrier-custom.yml"
SARIF_SCHEMA = HERE / "schema" / "sarif-schema-2.1.0.json"
SARIF_SCHEMA_URI = "https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/schemas/sarif-schema-2.1.0.json"

# Registry rulesets by language. The Semgrep registry has no XML pack
# (p/xml does not exist and r/xml is empty); r/java.servlets carries its only
# XML-language rules (web.xml). XML/XSLT coverage otherwise comes from the
# custom rules (carrier.xml-external-entity, carrier.xslt-external-resource,
# carrier.hardcoded-credential-config).
REGISTRY_RULESETS = {
    "java": "p/java",
    "xml": "r/java.servlets",
    "shell": "r/bash",
}

# Written as .semgrepignore at the root of the extracted tree. Build output and
# test sources are out of scope for the export.
EXCLUDES = [
    "**/target/",
    "**/build/",
    "**/node_modules/",
    "**/.mvn/",
    "**/src/test/",
    "**/*.min.js",
]

LEVELS = ("error", "warning", "note", "none")


def git(repo: Path, *args: str, binary: bool = False):
    out = subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True
    )
    return out.stdout if binary else out.stdout.decode().strip()


def read_paths(cli_paths: list[str], paths_file: str | None) -> list[str]:
    paths = list(cli_paths)
    if paths_file:
        for line in Path(paths_file).read_text().splitlines():
            line = line.split("#", 1)[0].strip()
            if line:
                paths.append(line)
    cleaned = []
    for p in paths:
        p = p.strip().removeprefix("./").rstrip("/")
        if not p or p.startswith("/") or ".." in Path(p).parts:
            raise SystemExit(f"path must be repository-relative: {p!r}")
        if p not in cleaned:
            cleaned.append(p)
    if not cleaned:
        raise SystemExit("no paths given (pass PATH arguments or --paths-file)")
    return cleaned


def repository_uri(repo: Path) -> str:
    try:
        url = git(repo, "remote", "get-url", "origin")
    except subprocess.CalledProcessError:
        return repo.resolve().as_uri()
    url = re.sub(r"//[^/@]*@", "//", url)  # drop any userinfo
    m = re.search(r"github\.com[/:]([^/]+)/([^/]+?)(\.git)?$", url)
    if m:
        return f"https://github.com/{m.group(1)}/{m.group(2)}"
    return url


def extract(repo: Path, commit: str, paths: list[str], dest: Path) -> None:
    for p in paths:
        if not git(repo, "ls-tree", "--name-only", commit, "--", p):
            raise SystemExit(f"{p} does not exist at {commit}")
    dest.mkdir(parents=True, exist_ok=True)
    archive = subprocess.run(
        ["git", "-C", str(repo), "archive", "--format=tar", commit, "--", *paths],
        check=True,
        capture_output=True,
    ).stdout
    subprocess.run(["tar", "-x", "-C", str(dest)], input=archive, check=True)
    (dest / ".semgrepignore").write_text("\n".join(EXCLUDES) + "\n")


def run_semgrep(
    root: Path, paths: list[str], configs: list[str], raw_out: Path
) -> None:
    semgrep = Path(sys.executable).with_name("semgrep")
    cmd = [
        str(semgrep) if semgrep.exists() else (shutil.which("semgrep") or "semgrep"),
        "scan",
        "--metrics",
        "off",
        "--disable-version-check",
        "--quiet",
        "--sarif",
        "--output",
        str(raw_out),
    ]
    for c in configs:
        cmd += ["--config", c]
    cmd += paths
    proc = subprocess.run(cmd, check=False, cwd=root)
    if proc.returncode not in (0, 1) or not raw_out.exists():
        raise SystemExit(f"semgrep failed with exit code {proc.returncode}")


def canonical_rule_id(rule_id: str) -> str:
    # Semgrep prefixes rules loaded from a local file with the file's dotted
    # path; the carrier's ids are stable from "carrier." onwards.
    i = rule_id.find("carrier.")
    return rule_id[i:] if i > 0 and rule_id[:i].endswith(".") else rule_id


PROMO_LINE = re.compile(
    r"^.*(Enable cross-file analysis|sg\.run/pro).*\n?", re.MULTILINE
)


def clean_rule(rule: dict) -> dict:
    raw_id = rule["id"]
    rid = canonical_rule_id(raw_id)
    text = json.dumps(rule)
    if rid != raw_id:
        text = text.replace(raw_id[: len(raw_id) - len(rid)], "")
    rule = json.loads(text)
    rule["id"] = rid
    if rule.get("name"):
        rule["name"] = rid
    rule["shortDescription"] = {"text": f"{TOOL_NAME} rule {rid}"}
    for key in ("help", "fullDescription"):
        for fmt in ("text", "markdown"):
            if fmt in rule.get(key, {}):
                rule[key][fmt] = PROMO_LINE.sub("", rule[key][fmt]).replace(
                    "[Semgrep Rule](", "[Rule reference]("
                )
    return rule


def fingerprint(res: dict) -> str:
    loc = res.get("locations", [{}])[0].get("physicalLocation", {})
    snippet = " ".join(loc.get("region", {}).get("snippet", {}).get("text", "").split())
    basis = "|".join(
        [res["ruleId"], loc.get("artifactLocation", {}).get("uri", ""), snippet]
    )
    return hashlib.sha256(basis.encode()).hexdigest()[:32]


def stamp(
    raw: dict,
    *,
    run_id: str,
    commit: str,
    paths: list[str],
    repo_uri: str,
    rulesets: list[str],
    started: dt.datetime,
    finished: dt.datetime,
) -> dict:
    """Rewrite a Semgrep SARIF log into a CarrierSAST export."""
    if len(raw.get("runs", [])) != 1:
        raise ValueError("expected exactly one SARIF run")
    run = raw["runs"][0]
    driver = run["tool"]["driver"]

    rules = []
    index_of = {}
    for rule in driver.get("rules", []):
        rule = clean_rule(rule)
        index_of[rule["id"]] = len(rules)
        rules.append(rule)

    results = []
    seen = set()
    for res in run.get("results", []):
        res = dict(res)
        res["ruleId"] = canonical_rule_id(res["ruleId"])
        if res["ruleId"] in index_of:
            res["ruleIndex"] = index_of[res["ruleId"]]
        else:
            res.pop("ruleIndex", None)
        if "level" not in res:
            rule = rules[index_of[res["ruleId"]]] if res["ruleId"] in index_of else {}
            res["level"] = rule.get("defaultConfiguration", {}).get("level", "warning")
        for loc in res.get("locations", []):
            art = loc.get("physicalLocation", {}).get("artifactLocation")
            if art is not None:
                art["uriBaseId"] = "SRCROOT"
        loc = res.get("locations", [{}])[0].get("physicalLocation", {})
        region = loc.get("region", {})
        key = (
            res["ruleId"],
            loc.get("artifactLocation", {}).get("uri"),
            region.get("startLine"),
            region.get("startColumn"),
        )
        if key in seen:  # constant-folded string concatenations report once per operand
            continue
        seen.add(key)
        res.pop("fingerprints", None)  # engine placeholder ("requires login")
        res["partialFingerprints"] = {"carrierSast/v1": fingerprint(res)}
        results.append(res)

    guid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"carriersast:{run_id}:{commit}"))
    out_run = {
        "tool": {
            "driver": {
                "name": TOOL_NAME,
                "fullName": f"{TOOL_NAME} static analysis",
                "organization": TOOL_ORGANIZATION,
                "version": TOOL_VERSION,
                "semanticVersion": TOOL_VERSION,
                "rules": rules,
            }
        },
        "automationDetails": {
            "id": f"{TOOL_NAME}/{run_id}",
            "guid": guid,
            "description": {
                "text": f"{TOOL_NAME} run {run_id} at {commit} over {', '.join(paths)}"
            },
        },
        "versionControlProvenance": [
            {
                "repositoryUri": repo_uri,
                "revisionId": commit,
                "mappedTo": {"uriBaseId": "SRCROOT"},
            }
        ],
        "originalUriBaseIds": {
            "SRCROOT": {"description": {"text": f"Repository root at commit {commit}"}}
        },
        "invocations": [
            {
                "executionSuccessful": all(
                    i.get("executionSuccessful", True)
                    for i in run.get("invocations", [])
                ),
                "startTimeUtc": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "endTimeUtc": finished.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "toolExecutionNotifications": [
                    n
                    for i in run.get("invocations", [])
                    for n in i.get("toolExecutionNotifications", [])
                ],
            }
        ],
        "results": results,
        "columnKind": run.get("columnKind", "utf16CodeUnits"),
        "properties": {
            "carrierSast": {
                "runId": run_id,
                "commit": commit,
                "scannedPaths": paths,
                "excludedPaths": EXCLUDES,
                "rulesets": rulesets,
            }
        },
    }
    return {"$schema": SARIF_SCHEMA_URI, "version": "2.1.0", "runs": [out_run]}


def validate(sarif: dict) -> None:
    schema = json.loads(SARIF_SCHEMA.read_text())
    jsonschema.Draft4Validator(schema).validate(sarif)


def summarize(sarif: dict) -> dict:
    results = sarif["runs"][0]["results"]
    by_rule = collections.Counter(r["ruleId"] for r in results)
    by_level = collections.Counter(r["level"] for r in results)
    by_rule_level = collections.Counter((r["ruleId"], r["level"]) for r in results)
    return {
        "total": len(results),
        "byLevel": {lvl: by_level.get(lvl, 0) for lvl in LEVELS},
        "byRule": [
            {"ruleId": rid, "level": lvl, "count": n}
            for (rid, lvl), n in sorted(
                by_rule_level.items(), key=lambda kv: (-kv[1], kv[0])
            )
        ],
        "rules": dict(by_rule),
    }


def print_summary(summary: dict, out=sys.stdout) -> None:
    print(f"total findings: {summary['total']}", file=out)
    print("by level:", file=out)
    for lvl, n in summary["byLevel"].items():
        print(f"  {lvl:<8} {n}", file=out)
    print("by rule:", file=out)
    for row in summary["byRule"]:
        print(f"  {row['count']:>4}  {row['level']:<8} {row['ruleId']}", file=out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("paths", nargs="*", help="repository-relative paths to scan")
    ap.add_argument(
        "--paths-file",
        help="file with one repository-relative path per line ('#' comments allowed)",
    )
    ap.add_argument(
        "--repo",
        default=".",
        help="git repository to read the commit from (default: .)",
    )
    ap.add_argument("--commit", default="HEAD", help="commit to scan (default: HEAD)")
    ap.add_argument(
        "--run-id", help="run id (default: CSAST-<UTC timestamp>-<short commit>)"
    )
    ap.add_argument(
        "--repository-uri",
        help="repositoryUri for versionControlProvenance (default: origin remote)",
    )
    ap.add_argument("--output", "-o", required=True, help="SARIF file to write")
    ap.add_argument(
        "--summary-json", help="also write the counts by rule and level as JSON"
    )
    ap.add_argument(
        "--no-registry", action="store_true", help="custom rules only (offline)"
    )
    args = ap.parse_args(argv)

    repo = Path(args.repo).resolve()
    paths = read_paths(args.paths, args.paths_file)
    commit = git(repo, "rev-parse", "--verify", f"{args.commit}^{{commit}}")
    started = dt.datetime.now(dt.UTC)
    run_id = args.run_id or f"CSAST-{started:%Y%m%dT%H%M%SZ}-{commit[:12]}"

    rulesets = ([] if args.no_registry else list(REGISTRY_RULESETS.values())) + [
        "carrier-custom"
    ]
    configs = [] if args.no_registry else list(REGISTRY_RULESETS.values())

    work = Path(tempfile.mkdtemp(prefix="carrier-sast-"))
    try:
        src = work / "src"
        src.mkdir()
        extract(repo, commit, paths, src)
        rules_dir = work / "rules"
        rules_dir.mkdir()
        shutil.copy(CUSTOM_RULES, rules_dir / CUSTOM_RULES.name)
        configs.append(str(rules_dir / CUSTOM_RULES.name))
        raw_out = work / "raw.sarif"
        run_semgrep(src, paths, configs, raw_out)
        raw = json.loads(raw_out.read_text())
    finally:
        shutil.rmtree(work, ignore_errors=True)
    finished = dt.datetime.now(dt.UTC)

    sarif = stamp(
        raw,
        run_id=run_id,
        commit=commit,
        paths=paths,
        repo_uri=args.repository_uri or repository_uri(repo),
        rulesets=rulesets,
        started=started,
        finished=finished,
    )
    validate(sarif)
    Path(args.output).write_text(json.dumps(sarif, indent=2) + "\n")

    summary = summarize(sarif)
    if args.summary_json:
        Path(args.summary_json).write_text(json.dumps(summary, indent=2) + "\n")
    print(
        f"{TOOL_NAME} {run_id} commit {commit} paths {' '.join(paths)} -> {args.output}",
        file=sys.stderr,
    )
    print_summary(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
