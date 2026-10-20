#!/usr/bin/env python3
"""Nightly dual run of the BizTalk claims hub: Saxon corpus against claims-hub-camel, message by message.

1. Checks out the fixture (demo-insurance once the fixture PR has merged, its branch until then) and runs
   `make deps && make check` there: 112 Saxon map outputs, 14 positional files, 16 triage results.
2. Checks out every claims-hub-camel ref (demo-insurance if it has the module, plus every open pull request
   into demo-insurance that touches it), copies the fixture in, hooks ByteComparison so each Camel output a
   golden test compares is kept, adds a triage capture test where the rules table exists, and runs
   `./mvnw verify` with -Dclaims.fixture.dir / -Dfixture.dir pointing at the fixture.
3. Compares every golden with every Camel output captured for it and writes report.md (one row per
   message, first differing byte, cause, totals at the bottom) and summary.json next to it.

Exit 0: every Camel output captured is byte-identical, the Saxon gate is green and every ref built.
Exit 1: at least one byte difference. Exit 2: nothing differs, but the Saxon gate, a Camel build or a Camel test is red.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

FIXTURE_DIR = "industries/insurance/biztalk-claims-intake"
CAMEL_DIR = "industries/insurance/claims-hub-camel"
FIXTURE_BRANCH = "devin/1792473658-insurance-biztalk-fixture"
BASE = "demo-insurance"
HERE = Path(__file__).resolve().parent
OVERLAY = HERE / "overlay"
HOOK = re.compile(r"(public static ByteComparison of\(byte\[\] (\w+), byte\[\] (\w+)\) \{)")


def run(cmd, cwd=None, env=None, log: Path | None = None, timeout=None) -> tuple[int, str]:
    proc = subprocess.run(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, timeout=timeout, shell=isinstance(cmd, str))
    if log:
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a") as fh:
            fh.write(f"$ {cmd if isinstance(cmd, str) else ' '.join(cmd)}\n{proc.stdout}\n[exit {proc.returncode}]\n")
    return proc.returncode, proc.stdout


def git(repo: Path, *args) -> str:
    code, out = run(["git", *args], cwd=repo)
    if code:
        raise RuntimeError(f"git {' '.join(args)}: {out.strip()}")
    return out.strip()


def ref_exists(repo: Path, ref: str) -> bool:
    return run(["git", "rev-parse", "--verify", "-q", ref + "^{commit}"], cwd=repo)[0] == 0


def path_in(repo: Path, ref: str, path: str) -> bool:
    return run(["git", "cat-file", "-e", f"{ref}:{path}"], cwd=repo)[0] == 0


def fetch(repo: Path) -> None:
    if git(repo, "rev-parse", "--is-shallow-repository") == "true":
        run(["git", "fetch", "-q", "--unshallow", "origin"], cwd=repo)
    git(repo, "fetch", "-q", "--prune", "origin")


def resolve_fixture(repo: Path) -> str:
    base, branch = f"origin/{BASE}", f"origin/{FIXTURE_BRANCH}"
    if not ref_exists(repo, branch):
        return base
    if run(["git", "merge-base", "--is-ancestor", branch, base], cwd=repo)[0] == 0:
        return base
    return branch


def open_prs(repo: Path) -> list[dict]:
    code, out = run(["gh", "pr", "list", "--state", "open", "--base", BASE, "--limit", "200",
                     "--json", "number,headRefName,title,url"], cwd=repo)
    if code:
        raise RuntimeError(f"gh pr list failed: {out.strip()}")
    return json.loads(out)


def discover_camel(repo: Path) -> list[dict]:
    refs = []
    if path_in(repo, f"origin/{BASE}", f"{CAMEL_DIR}/pom.xml"):
        refs.append({"ref": f"origin/{BASE}", "pr": None, "title": f"{BASE} (merged work)"})
    for pr in sorted(open_prs(repo), key=lambda p: p["number"]):
        head = f"origin/{pr['headRefName']}"
        if not ref_exists(repo, head) or not path_in(repo, head, f"{CAMEL_DIR}/pom.xml"):
            continue
        changed = git(repo, "diff", "--name-only", f"origin/{BASE}...{head}", "--", CAMEL_DIR)
        if changed:
            refs.append({"ref": head, "pr": pr["number"], "title": pr["title"], "url": pr["url"]})
    return refs


def worktree(repo: Path, ref: str, path: Path) -> str:
    if path.exists():
        run(["git", "worktree", "remove", "--force", str(path)], cwd=repo)
        shutil.rmtree(path, ignore_errors=True)
    git(repo, "worktree", "add", "--force", "--detach", str(path), ref)
    return git(path, "rev-parse", "HEAD")


# ---------------------------------------------------------------- Saxon side

def saxon_gate(fx: Path, logs: Path) -> dict:
    log = logs / "saxon-gate.log"
    deps, _ = run("make deps", cwd=fx, log=log)
    make, _ = run("make check", cwd=fx, log=log)
    steps = []
    for name, cmd, pattern in [
        ("maps", "python3 ../../../tools/xslt-golden/xslt_golden.py --manifest corpus/manifest.yaml check",
         r"total messages (\d+), failures (\d+)"),
        ("positional", "python3 tools/ff_render.py check", r"vendor-remittance-ff: (\d+) files, failures (\d+)"),
        ("triage", "python3 tools/triage_reference.py check", r"triage: (\d+) claims, failures (\d+)"),
    ]:
        code, out = run(cmd, cwd=fx, log=log)
        m = re.search(pattern, out)
        steps.append({"step": name, "command": cmd, "exit": code,
                      "units": int(m.group(1)) if m else None, "failures": int(m.group(2)) if m else None})
    return {"make_deps": deps, "make_check": make, "steps": steps,
            "green": deps == 0 and make == 0 and all(s["exit"] == 0 for s in steps)}


def saxon_units(fx: Path) -> list[dict]:
    import yaml

    manifest = yaml.safe_load((fx / "corpus/manifest.yaml").read_text())
    base = (fx / "corpus" / manifest.get("base", "..")).resolve()
    units = []
    for spec in manifest["maps"]:
        for f in sorted((base / spec["golden"]).iterdir()):
            if f.is_file():
                units.append({"kind": "map", "group": spec["name"], "message": f.stem, "path": f})
    for f in sorted((fx / "corpus/golden/vendor-remittance-ff").iterdir()):
        units.append({"kind": "positional", "group": "VendorRemittanceFile", "message": f.stem, "path": f})
    for f in sorted((fx / "corpus/golden/triage").glob("*.json")):
        units.append({"kind": "triage", "group": "ClaimTriage", "message": f.stem, "path": f})
    for u in units:
        u["bytes"] = u["path"].read_bytes()
        u["sha"] = hashlib.sha256(u["bytes"]).hexdigest()
    return units


# ---------------------------------------------------------------- Camel side

def apply_overlays(cam: Path, with_overlays: bool) -> dict:
    applied = {"byte_capture": False, "triage_capture": False}
    if not with_overlays:
        return applied
    bc = cam / "src/test/java/example/claimshub/golden/ByteComparison.java"
    if bc.exists():
        text = bc.read_text()
        m = HOOK.search(text)
        if m:
            bc.write_text(text[:m.end()] + f"\n        DualRunCapture.capture({m.group(2)}, {m.group(3)});" + text[m.end():])
            shutil.copy(OVERLAY / "DualRunCapture.java", bc.parent / "DualRunCapture.java")
            applied["byte_capture"] = True
    for evaluator in (cam / "src/main/java").rglob("TriageEvaluator.java"):
        pkg = re.search(r"^package ([\w.]+);", evaluator.read_text(), re.M)
        siblings = all((evaluator.parent / n).exists() for n in ("RulesTable.java", "TriageFactsReader.java", "TriageResult.java"))
        if pkg and siblings and (cam / "src/main/resources/rules/claim-triage.csv").exists():
            dest = cam / "src/test/java" / pkg.group(1).replace(".", "/")
            dest.mkdir(parents=True, exist_ok=True)
            src = (OVERLAY / "DualRunTriageCaptureTest.java").read_text().replace("__PACKAGE__", pkg.group(1))
            (dest / "DualRunTriageCaptureTest.java").write_text(src)
            applied["triage_capture"] = True
            break
    return applied


def prepull_images(cam: Path, log: Path) -> None:
    """Docker Hub rate-limits this network; pull bare image names from mirror.gcr.io and tag them."""
    names = set()
    for f in (cam / "src/test").rglob("*.java"):
        names.update(re.findall(r'"((?:[a-z0-9-]+/)?[a-z0-9._-]+:[A-Za-z0-9._-]+)"', f.read_text()))
    for name in sorted(names):
        repo = name.split(":")[0]
        if repo.startswith(("mock", "ns0", "xmlns", "direct", "log", "seda", "file", "sftp", "smtp", "http")) or "." in repo.split("/")[0]:
            continue
        if run(["docker", "image", "inspect", name])[0] == 0:
            continue
        mirror = "mirror.gcr.io/" + (name if "/" in repo else "library/" + name)
        if run(["docker", "pull", "-q", mirror], log=log)[0] == 0:
            run(["docker", "tag", mirror, name], log=log)


def containers() -> set[str]:
    code, out = run(["docker", "ps", "-q", "--no-trunc"])
    return set(out.split()) if code == 0 else set()


def surefire(cam: Path) -> dict:
    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0, "suites": 0, "failed": []}
    for xml in sorted((cam / "target/surefire-reports").glob("TEST-*.xml")) + sorted((cam / "target/failsafe-reports").glob("TEST-*.xml")):
        try:
            root = ET.parse(xml).getroot()
        except ET.ParseError:
            continue
        totals["suites"] += 1
        for k in ("tests", "failures", "errors", "skipped"):
            totals[k] += int(root.get(k, 0))
        for case in root.iter("testcase"):
            bad = case.find("failure") if case.find("failure") is not None else case.find("error")
            if bad is not None:
                message = " ".join((bad.get("message") or bad.text or "").split())[:400]
                totals["failed"].append(f"{case.get('classname', '').rsplit('.', 1)[-1]}.{case.get('name')}: {message}")
    return totals


def camel_run(repo: Path, target: dict, fx: Path, work: Path, logs: Path, args) -> dict:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", target["ref"].removeprefix("origin/"))[-60:]
    wt = work / "camel" / slug
    result = dict(target, slug=slug, sha=worktree(repo, target["ref"], wt))
    cam = wt / CAMEL_DIR
    wt_fx = wt / FIXTURE_DIR
    shutil.rmtree(wt_fx, ignore_errors=True)
    shutil.copytree(fx, wt_fx, symlinks=True)
    log = logs / f"camel-{slug}.log"
    env = dict(os.environ, TESTCONTAINERS_RYUK_DISABLED="true")
    if args.java_home:
        env["JAVA_HOME"] = args.java_home
        env["PATH"] = f"{args.java_home}/bin:{env['PATH']}"
    if args.maven_mirror:
        env["MVNW_REPOURL"] = args.maven_mirror
    prepull_images(cam, log)
    cmd = ["./mvnw", "-B", "-ntp", "verify", "-Dmaven.test.failure.ignore=true",
           f"-Dclaims.fixture.dir={wt_fx}", f"-Dfixture.dir={wt_fx}"]
    if args.maven_settings:
        cmd += ["-s", args.maven_settings]
    before = containers()
    for with_overlays in (True, False):
        result["overlays"] = apply_overlays(cam, with_overlays)
        code, out = run(cmd, cwd=cam, env=env, log=log, timeout=args.maven_timeout)
        broke_overlay = code != 0 and "DualRun" in out and "COMPILATION ERROR" in out
        if not broke_overlay:
            break
        git(wt, "checkout", "--", CAMEL_DIR)
        git(wt, "clean", "-fdq", "--", CAMEL_DIR)
        result["overlay_note"] = "capture overlay did not compile against this ref; ran without it"
    stray = containers() - before
    for cid in stray:
        run(["docker", "rm", "-f", cid], log=log)
    result.update(maven_exit=code, tests=surefire(cam), containers_stopped=len(stray),
                  build_failed="BUILD FAILURE" in out and not (cam / "target/surefire-reports").exists())
    result["captures"] = read_captures(cam)
    result["triage"] = read_triage(cam)
    result["causes"] = read_causes(cam)
    reports = logs / "golden-report" / slug
    for d in ("target/golden-report", "target/parity"):
        if (cam / d).exists():
            shutil.copytree(cam / d, reports / Path(d).name, dirs_exist_ok=True)
    return result


def read_captures(cam: Path) -> list[dict]:
    d = cam / "target/dual-run/capture"
    rows = []
    if (d / "index.tsv").exists():
        for line in (d / "index.tsv").read_text().splitlines():
            golden, actual, caller, name = line.split("\t")
            rows.append({"golden_sha": golden, "caller": caller, "bytes": (d / name).read_bytes()})
    return rows


def read_triage(cam: Path) -> dict[str, bytes]:
    out = {}
    for f in sorted((cam / "target/dual-run/triage").glob("*.json")):
        raw = json.loads(f.read_text())
        layout = {k: raw.get(k) for k in ("ClaimNumber", "Outcome", "Reasons", "RulesFired")}
        out[f.stem] = (json.dumps(layout, indent=2) + "\n").encode("utf-8")
    return out


def read_causes(cam: Path) -> dict[str, str]:
    """Message -> cause from the Camel tests' own golden reports (last cell of a row whose verdict is red)."""
    causes = {}
    for md in (cam / "target/golden-report").glob("*.md"):
        for line in md.read_text().splitlines():
            cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip())[1:-1]]
            if len(cells) >= 3 and cells[-1] and not cells[0].startswith(("**", "---", "Message", "Instruction")):
                causes[f"{md.stem}:{Path(cells[0]).stem}"] = cells[-1].replace("\\|", "|")
    return causes


# ---------------------------------------------------------------- comparison

def first_difference(a: bytes, b: bytes) -> dict | None:
    limit = min(len(a), len(b))
    at = next((i for i in range(limit) if a[i] != b[i]), limit)
    if at == limit and len(a) == len(b):
        return None
    line = a[:at].count(b"\n") + 1
    col = at - (a.rfind(b"\n", 0, at) + 1) + 1

    def byte(x: bytes) -> str:
        return "end of output" if at >= len(x) else f"0x{x[at]:02X} {chr(x[at])!r}" if 32 <= x[at] < 127 else f"0x{x[at]:02X}"

    def excerpt(x: bytes) -> str:
        return x[max(0, at - 12):at + 28].decode("utf-8", "replace").replace("\r", "\\r").replace("\n", "\\n").replace("|", "\\|")

    return {"offset": at, "line": line, "column": col, "saxon_byte": byte(a), "camel_byte": byte(b),
            "saxon_excerpt": excerpt(a), "camel_excerpt": excerpt(b)}


def triage_fields(a: bytes, b: bytes) -> str:
    x, y = json.loads(a), json.loads(b)
    diff = [k for k in ("Outcome", "Reasons", "RulesFired") if x.get(k) != y.get(k)]
    return "fields differ: " + ", ".join(f"{k} Saxon {x.get(k)!r} vs Camel {y.get(k)!r}" for k in diff) if diff else ""


def compare(units: list[dict], camel: list[dict]) -> list[dict]:
    by_sha: dict[str, list[dict]] = {}
    for u in units:
        u["observations"] = []
        by_sha.setdefault(u["sha"], []).append(u)
    for r in camel:
        for cap in r["captures"]:
            for u in by_sha.get(cap["golden_sha"], []):
                u["observations"].append({"slug": r["slug"], "pr": r["pr"], "caller": cap["caller"], "bytes": cap["bytes"]})
        for claim, payload in r["triage"].items():
            for u in units:
                if u["kind"] == "triage" and u["message"] == claim:
                    u["observations"].append({"slug": r["slug"], "pr": r["pr"], "caller": "DualRunTriageCaptureTest", "bytes": payload})
    causes = {(r["slug"], k): v for r in camel for k, v in r["causes"].items()}
    rows = []
    for u in units:
        seen, obs = set(), []
        for o in u["observations"]:
            key = (o["slug"], o["caller"], hashlib.sha256(o["bytes"]).hexdigest())
            if key not in seen:
                seen.add(key)
                o["diff"] = first_difference(u["bytes"], o["bytes"])
                obs.append(o)
        red = [o for o in obs if o["diff"]]
        pick = red[0] if red else (obs[0] if obs else None)
        cause = ""
        if red:
            o = red[0]
            group = "VendorRemittanceFile" if u["kind"] == "positional" else u["group"]
            cause = causes.get((o["slug"], f"{group}:{u['message']}"), "")
            if u["kind"] == "triage":
                cause = cause or triage_fields(u["bytes"], o["bytes"])
            cause = cause or "no cause recorded by the Camel test"
        rows.append({"kind": u["kind"], "group": u["group"], "message": u["message"],
                     "saxon_len": len(u["bytes"]), "saxon_sha": u["sha"],
                     "camel_len": len(pick["bytes"]) if pick else None,
                     "camel_sha": hashlib.sha256(pick["bytes"]).hexdigest() if pick else None,
                     "sources": [f"{'#' + str(o['pr']) if o['pr'] else o['slug']} {o['caller']} {'differs' if o['diff'] else 'identical'}" for o in obs],
                     "diff": pick["diff"] if pick else None,
                     "verdict": "not covered" if not obs else ("red" if red else "green"), "cause": cause})
    return rows


# ---------------------------------------------------------------- report

def render(meta: dict, gate: dict, camel: list[dict], rows: list[dict]) -> str:
    out = [f"# Claims hub dual run, {meta['date']}", "",
           f"Fixture `{meta['fixture_ref']}` @ `{meta['fixture_sha'][:12]}`. Harness `{meta['harness_sha'][:12]}`.", "",
           "## Saxon gate (`make deps && make check`)", "",
           "| Step | Command | Units | Failures | Exit | Verdict |", "| --- | --- | ---: | ---: | ---: | --- |"]
    for s in gate["steps"]:
        out.append(f"| {s['step']} | `{s['command']}` | {s['units']} | {s['failures']} | {s['exit']} | {'green' if s['exit'] == 0 else '**red**'} |")
    out.append(f"| **make check** | | | | {gate['make_check']} | {'**green**' if gate['green'] else '**red**'} |")
    out += ["", "## Camel golden tests (`./mvnw verify`)", "",
            "| Ref | PR | Commit | Tests | Failed | Errors | Skipped | Outputs captured | Containers stopped | Verdict |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    for r in camel:
        t = r["tests"]
        cap = len(r["captures"]) + len(r["triage"])
        ok = not r["build_failed"] and t["failures"] == 0 and t["errors"] == 0
        note = r.get("overlay_note", "")
        out.append(f"| `{r['ref'].removeprefix('origin/')}` | {('#' + str(r['pr'])) if r['pr'] else ''} | `{r['sha'][:12]}` | {t['tests']} | "
                   f"{t['failures']} | {t['errors']} | {t['skipped']} | {cap} | {r['containers_stopped']} | "
                   f"{'green' if ok else ('**build failed**' if r['build_failed'] else '**red**')}{' (' + note + ')' if note else ''} |")
    failing = [(r, f) for r in camel for f in r["tests"]["failed"]]
    if failing:
        out += ["", "### Red Camel tests (not a Saxon/Camel byte difference, but not green)", "",
                "| Ref | Test | Failure |", "| --- | --- | --- |"]
        for r, f in failing:
            test, _, message = f.partition(": ")
            out.append(f"| `{r['ref'].removeprefix('origin/')}` | {test} | {message.replace('|', '\\|')} |")
    out += ["", "## Per message", "",
            "Saxon = the committed golden, which `make check` has just reproduced with Saxon. Camel = the output the Camel golden test "
            "compared with that golden (first differing ref shown; every ref that produced it is listed). First differing byte is a "
            "0-based offset into the Saxon bytes.", "",
            "| # | Kind | Map / file | Message | Saxon (bytes, sha256) | Camel (bytes, sha256) | Produced by | First differing byte | Verdict | Cause |",
            "| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for i, r in enumerate(rows, 1):
        camel_val = f"{r['camel_len']} B `{r['camel_sha'][:12]}`" if r["camel_sha"] else "no output"
        d = r["diff"]
        diff = (f"byte {d['offset']} (line {d['line']}, col {d['column']}): Saxon {d['saxon_byte']} vs Camel {d['camel_byte']}; "
                f"Saxon `{d['saxon_excerpt']}` / Camel `{d['camel_excerpt']}`") if d else ("none" if r["camel_sha"] else "n/a")
        verdict = {"green": "green", "red": "**red**", "not covered": "not covered"}[r["verdict"]]
        out.append(f"| {i} | {r['kind']} | {r['group']} | {r['message']} | {r['saxon_len']} B `{r['saxon_sha'][:12]}` | {camel_val} | "
                   f"{'<br>'.join(r['sources']) or 'no Camel ref implements it yet'} | {diff} | {verdict} | {r['cause'].replace('|', '\\|')} |")
    out += ["", "## Totals", "", "| Kind | Messages | Green | Red | Not covered |", "| --- | ---: | ---: | ---: | ---: |"]
    for kind in ("map", "positional", "triage", None):
        sel = [r for r in rows if kind is None or r["kind"] == kind]
        label = f"**all**" if kind is None else kind
        out.append(f"| {label} | {len(sel)} | {sum(r['verdict'] == 'green' for r in sel)} | {sum(r['verdict'] == 'red' for r in sel)} | "
                   f"{sum(r['verdict'] == 'not covered' for r in sel)} |")
    out += ["", f"Exit status: **{meta['status']}** ({meta['status_text']})."]
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=str(HERE.parents[2]), help="otterworks checkout (default: this one)")
    ap.add_argument("--work", default=str(Path.home() / "claims-hub-dual-run"), help="worktrees and output")
    ap.add_argument("--fixture-ref", help="override the fixture ref (default: demo-insurance once merged, else the fixture branch)")
    ap.add_argument("--camel-ref", action="append", help="claims-hub-camel ref to run; repeatable (default: discover)")
    ap.add_argument("--java-home", default=os.environ.get("JAVA_HOME"))
    ap.add_argument("--maven-mirror", default=os.environ.get("MVNW_REPOURL"))
    ap.add_argument("--maven-settings")
    ap.add_argument("--maven-timeout", type=int, default=1800)
    ap.add_argument("--no-fetch", action="store_true")
    args = ap.parse_args()

    repo, work = Path(args.repo).resolve(), Path(args.work).resolve()
    out_dir = work / "out"
    shutil.rmtree(out_dir, ignore_errors=True)
    logs = out_dir / "logs"
    logs.mkdir(parents=True)
    if not args.no_fetch:
        fetch(repo)
    fixture_ref = args.fixture_ref or resolve_fixture(repo)
    fx_wt = work / "fixture"
    fixture_sha = worktree(repo, fixture_ref, fx_wt)
    fx = fx_wt / FIXTURE_DIR
    gate = saxon_gate(fx, logs)
    units = saxon_units(fx)
    targets = [{"ref": r, "pr": None, "title": r} for r in args.camel_ref] if args.camel_ref else discover_camel(repo)
    camel = []
    for t in targets:
        print(f"camel: {t['ref']}", flush=True)
        try:
            camel.append(camel_run(repo, t, fx, work, logs, args))
        except Exception as e:  # noqa: BLE001 - a broken ref is reported, not fatal
            camel.append(dict(t, slug=t["ref"], sha="?" * 12, tests=surefire(Path("/nonexistent")), captures=[], triage={},
                              causes={}, containers_stopped=0, build_failed=True, maven_exit=None, overlay_note=f"harness error: {e}"))
    rows = compare(units, camel)
    red = sum(r["verdict"] == "red" for r in rows)
    broken = (not gate["green"]) or any(c["build_failed"] or c["tests"]["errors"] or c["tests"]["failures"] for c in camel) or not camel
    status = 1 if red else (2 if broken else 0)
    meta = {"date": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "fixture_ref": fixture_ref,
            "fixture_sha": fixture_sha, "harness_sha": git(HERE, "rev-parse", "HEAD"), "status": status,
            "status_text": {0: "every captured Camel output is byte-identical to Saxon", 1: f"{red} message(s) differ",
                            2: "no byte difference, but the Saxon gate, a Camel build or a Camel test is red"}[status]}
    (out_dir / "report.md").write_text(render(meta, gate, camel, rows))
    summary = {"meta": meta, "gate": gate,
               "camel": [{k: v for k, v in c.items() if k not in ("captures", "triage", "causes")} for c in camel],
               "rows": rows, "totals": {v: sum(r["verdict"] == v for r in rows) for v in ("green", "red", "not covered")}}
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    for t in camel:
        if t.get("slug") and (work / "camel" / t["slug"]).exists():
            run(["git", "worktree", "remove", "--force", str(work / "camel" / t["slug"])], cwd=repo)
    run(["git", "worktree", "remove", "--force", str(fx_wt)], cwd=repo)
    print(f"{meta['status_text']}; report: {out_dir / 'report.md'}")
    return status


if __name__ == "__main__":
    sys.exit(main())
