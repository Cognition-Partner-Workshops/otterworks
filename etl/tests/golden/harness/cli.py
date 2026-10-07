"""record / check / repeat legacy ETL goldens.

  python -m harness --script analytics_daily --mode check
  python -m harness --script all --mode repeat

record  run each scenario and (re)write <script>/<scenario>/golden/*.json
check   run each scenario and diff the normalized snapshot against golden/
repeat  run each scenario twice and require byte-identical normalized snapshots

Once a script is retired (removed from etl/scripts/, etl/RUNBOOK.md section 9), check
and repeat skip its legacy run and only validate the committed goldens (every surface
present, valid JSON), which stay as the DAG's contract for `make etl-parity`. record needs
the legacy script: restore it from git history first (etl/RUNBOOK.md section 9.3).
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import sys
import time
from collections.abc import Callable
from pathlib import Path

from . import config_ini, infra, normalize, runner, scenario, settings, snapshot
from .stub_http import ServiceStub

SHIM_BANNER = "[golden-shim] endpoint="
SHIM_FAILURE_EXIT_CODE = 97
DIFF_FILE = "diff.txt"


class HarnessError(RuntimeError):
    pass


Run = Callable[[Path, str], runner.RunResult]

# One file per surface harness/snapshot.py captures.
GOLDEN_SURFACES = (
    "dynamodb.json",
    "meilisearch.json",
    "postgres.json",
    "result.json",
    "s3.json",
    "sqs.json",
)


def legacy_script(script: str) -> Path:
    return settings.ETL_DIR / "scripts" / ("%s.py" % script)


def is_retired(script: str) -> bool:
    return not legacy_script(script).is_file()


def require_legacy_runtime(scn: scenario.Scenario, mode: str) -> None:
    missing = [
        str(path.relative_to(settings.REPO_ROOT))
        for path in (legacy_script(scn.script), settings.ETL_DIR / "run.sh")
        if not path.is_file()
    ]
    if missing:
        raise HarnessError(
            "%s: %s mode runs the legacy script, but %s %s retired; restore it from "
            "git history first (etl/RUNBOOK.md section 9.3)"
            % (
                scn.label,
                mode,
                " and ".join(missing),
                "are" if len(missing) > 1 else "is",
            )
        )


def check_retired(scn: scenario.Scenario) -> tuple[bool, str]:
    """Check/repeat of a retired script: every golden surface must be there and parse."""
    golden = read_golden(scn)
    if not golden:
        return False, "script retired and no golden recorded"
    missing = [name for name in GOLDEN_SURFACES if name not in golden]
    if missing:
        return False, "script retired; golden incomplete, missing %s" % ", ".join(
            missing
        )
    for name, content in golden.items():
        try:
            json.loads(content)
        except json.JSONDecodeError as exc:
            return False, "script retired; golden/%s is not valid JSON (%s)" % (
                name,
                exc,
            )
    return True, (
        "SKIP legacy run: script retired; %d golden file(s) kept as the DAG contract "
        "sha256=%s" % (len(golden), digest(golden)[:16])
    )


def run_scenario(
    scn: scenario.Scenario,
    image: str,
    attempt: int,
    run: Run | None = None,
    run_dir: Path | None = None,
) -> tuple[dict[str, str], int, int]:
    """Reset, seed, run once; return (rendered files, exit code, replaced).

    By default the legacy script runs in the pinned image and its log must
    carry the shim banner. The DAG parity runner passes ``run`` (called with
    the generated config.ini and the HTTP stub URL) and its own ``run_dir``;
    seeding, snapshot and normalization stay exactly the same.
    """
    run_dir = run_dir or settings.RUNS_DIR / scn.script / scn.name
    run_dir.mkdir(parents=True, exist_ok=True)
    infra.reset()
    infra.ensure_resources()
    infra.seed(scn.seed)
    with ServiceStub(scn.seed.get("http")) as stub:
        config_path = run_dir / "config.ini"
        config_path.write_text(config_ini.render(stub.url, scn.config_overrides))
        config_path.chmod(0o644)
        started = time.monotonic()
        if run is None:
            result = runner.run(image, scn.script, scn.frozen_time, config_path)
        else:
            result = run(config_path, stub.url)
        elapsed = time.monotonic() - started
    log_path = run_dir / ("run-%d.log" % attempt)
    log_path.write_text(result.output)
    if run is None and (
        result.exit_code == SHIM_FAILURE_EXIT_CODE or SHIM_BANNER not in result.output
    ):
        raise HarnessError(
            "%s: sitecustomize shim did not load; see %s" % (scn.label, log_path)
        )
    files, replaced = normalize.normalize(snapshot.capture(result.exit_code))
    rendered = snapshot.render(files)
    write_files(run_dir / ("snapshot-%d" % attempt), rendered)
    print(
        "  run %d: exit=%d in %.1fs, %d volatile value(s) normalized, log %s"
        % (
            attempt,
            result.exit_code,
            elapsed,
            replaced,
            log_path.relative_to(settings.REPO_ROOT),
        )
    )
    return rendered, result.exit_code, replaced


def digest(files: dict[str, str]) -> str:
    h = hashlib.sha256()
    for name, content in sorted(files.items()):
        h.update(name.encode() + b"\0" + content.encode() + b"\0")
    return h.hexdigest()


def diff(
    expected: dict[str, str], actual: dict[str, str], max_lines: int = 200
) -> list[str]:
    lines: list[str] = []
    for name in sorted(set(expected) | set(actual)):
        a, b = expected.get(name), actual.get(name)
        if a == b:
            continue
        lines.extend(
            difflib.unified_diff(
                (a or "").splitlines(keepends=True),
                (b or "").splitlines(keepends=True),
                fromfile="golden/%s" % name if a is not None else "/dev/null",
                tofile="actual/%s" % name if b is not None else "/dev/null",
            )
        )
    if len(lines) > max_lines:
        lines = lines[:max_lines] + [
            "... (%d more diff lines)\n" % (len(lines) - max_lines)
        ]
    return lines


def read_golden(scn: scenario.Scenario) -> dict[str, str]:
    if not scn.golden_dir.is_dir():
        return {}
    return {p.name: p.read_text() for p in sorted(scn.golden_dir.glob("*.json"))}


def write_files(directory: Path, files: dict[str, str]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for stale in directory.glob("*.json"):
        if stale.name not in files:
            stale.unlink()
    for name, content in files.items():
        (directory / name).write_text(content)


def write_golden(scn: scenario.Scenario, files: dict[str, str]) -> None:
    write_files(scn.golden_dir, files)


def report_diff(scn: scenario.Scenario, lines: list[str]) -> None:
    """Print a diff and keep it next to the run logs for the CI artifact."""
    sys.stdout.writelines(lines)
    (settings.RUNS_DIR / scn.script / scn.name / DIFF_FILE).write_text("".join(lines))


def execute(scn: scenario.Scenario, image: str | None, mode: str) -> tuple[bool, str]:
    print("== %s [%s] frozen_time=%s" % (scn.label, mode, scn.frozen_time))
    if mode in ("check", "repeat") and is_retired(scn.script):
        return check_retired(scn)
    require_legacy_runtime(scn, mode)
    assert image is not None
    (settings.RUNS_DIR / scn.script / scn.name / DIFF_FILE).unlink(missing_ok=True)
    files, exit_code, _ = run_scenario(scn, image, 1)
    if mode == "record":
        write_golden(scn, files)
        return True, "recorded exit=%d sha256=%s" % (exit_code, digest(files)[:16])
    if mode == "check":
        golden = read_golden(scn)
        if not golden:
            return False, "no golden recorded (run MODE=record)"
        delta = diff(golden, files)
        if delta:
            report_diff(scn, delta)
            return False, "differs from golden"
        return True, "identical to golden sha256=%s" % digest(files)[:16]
    second, _, _ = run_scenario(scn, image, 2)
    first_digest, second_digest = digest(files), digest(second)
    print("  run 1 sha256=%s\n  run 2 sha256=%s" % (first_digest, second_digest))
    if files != second:
        report_diff(scn, diff(files, second))
        return False, "runs differ"
    return True, "byte-identical across 2 runs sha256=%s" % first_digest[:16]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m harness",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--script", required=True, help="script name without .py, or 'all'"
    )
    parser.add_argument("--scenario", help="only this scenario")
    parser.add_argument(
        "--mode", choices=("record", "check", "repeat"), default="check"
    )
    args = parser.parse_args(argv)

    scenarios = scenario.discover(args.script, args.scenario)
    if not scenarios:
        print(
            "no scenarios found for script=%s scenario=%s"
            % (args.script, args.scenario or "*"),
            file=sys.stderr,
        )
        return 2

    if args.mode == "record":
        try:
            for scn in scenarios:
                require_legacy_runtime(scn, args.mode)
        except HarnessError as exc:
            print(exc, file=sys.stderr)
            return 2

    image = None
    if args.mode == "record" or not all(is_retired(s.script) for s in scenarios):
        infra.wait_ready()
        infra.ensure_resources()
        image = runner.ensure_image()
        print("legacy image %s" % image)

    results = []
    for scn in scenarios:
        try:
            ok, detail = execute(scn, image, args.mode)
        except HarnessError as exc:
            ok, detail = False, str(exc)
        results.append((scn.label, ok, detail))

    print("\n| scenario | mode | result |\n|---|---|---|")
    for label, ok, detail in results:
        print(
            "| %s | %s | %s: %s |"
            % (label, args.mode, "PASS" if ok else "FAIL", detail)
        )
    return 0 if all(ok for _, ok, _ in results) else 1
