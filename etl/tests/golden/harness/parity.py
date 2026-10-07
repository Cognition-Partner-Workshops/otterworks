"""DAG parity: run committed scenarios against an Airflow DAG and diff with the legacy goldens.

  python -m harness.parity --script audit_archive_weekly
  python -m harness.parity --script audit_archive_weekly --dag parity_wrong__audit_archive_weekly --expect failed
  python -m harness.parity --script storage_cleanup_daily --variant reference_mismatches_normalize_keys

Per scenario: reset and seed exactly like the golden harness, run
`airflow dags test <dag_id> <frozen_time>` in a container of the Airflow image
(harness/airflow_container.py), snapshot and normalize with the same code, then
split golden and DAG snapshots into checks (harness/differences.py). The DAG
for a script comes from parity/dags.yaml; accepted differences and flag-on
variants from <script>/accepted_differences.yaml.

Writes .runs/parity/<dag_id>/<script>/<all|scenario|variant>/report.md (the org parity table) and
report.json. Exit 0 when --expect identical (default) and no check failed, or
when --expect failed and at least one check failed without a harness error.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

from . import airflow_container, cli, differences, infra, runner, scenario, settings
from .differences import FAILED, Row

REGISTRY = airflow_container.PARITY_DIR / "dags.yaml"
HARNESS_ERROR = "harness error"


@dataclass(frozen=True)
class DagEntry:
    script: str
    dag_id: str
    dag_folder: str
    variants: bool

    @property
    def subdir(self) -> Path | None:
        return airflow_container.TOY_DAG_FOLDER if self.dag_folder == "toy" else None


@dataclass(frozen=True)
class Case:
    scn: scenario.Scenario
    label: str
    variables: dict
    accepted: tuple


def load_registry(
    path: Path = REGISTRY,
) -> tuple[dict[str, DagEntry], dict[str, DagEntry]]:
    data = yaml.safe_load(path.read_text())
    scripts, controls = {}, {}
    for script, raw in (data.get("scripts") or {}).items():
        scripts[script] = DagEntry(
            script, raw["dag_id"], raw["dag_folder"], bool(raw["variants"])
        )
    for dag_id, raw in (data.get("controls") or {}).items():
        controls[dag_id] = DagEntry(raw["script"], dag_id, raw["dag_folder"], False)
    for entry in [*scripts.values(), *controls.values()]:
        if entry.script not in settings.SCRIPTS or entry.dag_folder not in (
            "toy",
            "image",
        ):
            raise ValueError("%s: bad entry %s" % (path, entry))
    return scripts, controls


def resolve_dag(script: str, dag_id: str | None) -> DagEntry:
    scripts, controls = load_registry()
    if dag_id is None:
        if script not in scripts:
            raise SystemExit("no DAG registered for %s in %s" % (script, REGISTRY))
        return scripts[script]
    for entry in [*scripts.values(), *controls.values()]:
        if entry.dag_id == dag_id and entry.script == script:
            return entry
    raise SystemExit(
        "DAG %s is not registered for %s in %s" % (dag_id, script, REGISTRY)
    )


def cases(
    script: str, entry: DagEntry, only_scenario: str | None, only_variant: str | None
) -> list[Case]:
    accepted = differences.load(script)
    by_name = {s.name: s for s in scenario.discover(script)}
    out = []
    if only_variant is None:
        for scn in by_name.values():
            if only_scenario in (None, scn.name):
                out.append(Case(scn, scn.label, {}, accepted.for_scenario(scn.name)))
    if only_variant is not None or (entry.variants and only_scenario is None):
        for v in accepted.variants:
            if only_variant not in (None, v.name):
                continue
            base = by_name[v.scenario]
            scn = dataclasses.replace(base, name=v.name)
            label = "%s/%s (%s + %s)" % (
                script,
                v.name,
                v.scenario,
                ", ".join(
                    "%s=%s" % (k, airflow_container.variable_value(x))
                    for k, x in v.variables.items()
                ),
            )
            out.append(Case(scn, label, v.variables, v.accepted))
        if only_variant is not None and not out:
            raise SystemExit(
                "no variant %r in %s" % (only_variant, differences.ACCEPTED_FILE)
            )
    return out


def run_case(
    case: Case, entry: DagEntry, container, legacy_image: str, out_dir: Path
) -> tuple[list[Row], dict]:
    run_dir = out_dir / case.scn.name
    meta: dict = {"variables": {}}

    def run(config_path: Path, services_url: str) -> runner.RunResult:
        env = airflow_container.run_environment(
            services_url,
            case.variables,
            config_path,
            case.scn.frozen_time,
            legacy_image,
            case.scn.config_overrides,
        )
        result = container.dags_test(
            entry.dag_id, case.scn.frozen_time, env, entry.subdir
        )
        meta["variables"] = airflow_container.variables_read(result.output)
        return result

    golden = {k: json.loads(v) for k, v in cli.read_golden(case.scn).items()}
    if not golden:
        raise cli.HarnessError("%s: no golden recorded" % case.label)
    rendered, exit_code, _ = cli.run_scenario(
        case.scn, legacy_image, 1, run=run, run_dir=run_dir
    )
    log = (run_dir / "run-1.log").read_text()
    if entry.dag_folder == "toy" and cli.SHIM_BANNER not in log:
        raise cli.HarnessError(
            "%s: legacy shim banner missing from the DAG run log" % case.label
        )
    actual = {k: json.loads(v) for k, v in rendered.items()}
    meta["exit_code"] = exit_code
    rows = override_rows(case, meta["variables"])
    return rows + differences.classify(case.label, golden, actual, case.accepted), meta


def override_rows(case: Case, read: dict[str, list]) -> list[Row]:
    """One check per Variable override: the DAG must have read it, with the override value."""
    rows = []
    for key, value in case.variables.items():
        want = airflow_container.variable_value(value)
        seen = read.get(key, [])
        check = "Airflow Variable %s as read by the DAG" % key
        if seen and all(v == want for v in seen):
            rows.append(Row(case.label, check, want, want, differences.IDENTICAL))
        else:
            after = (
                " / ".join(sorted({str(v) for v in seen}))
                if seen
                else differences.ABSENT
            )
            reason = (
                "the DAG read a different value than the per-scenario override"
                if seen
                else "the DAG never read this Variable, so the override did not reach it"
            )
            rows.append(Row(case.label, check, want, after, FAILED, reason))
    return rows


def report(
    script: str,
    entry: DagEntry,
    image_info: str,
    results: list[tuple[Case, list[Row], dict]],
) -> str:
    rows = [r for _, case_rows, _ in results for r in case_rows]
    totals = differences.summary(rows)
    verdict = "PASS" if totals[FAILED] == 0 else "FAIL"
    lines = [
        "## DAG parity: `%s` legacy goldens vs DAG `%s`" % (script, entry.dag_id),
        "",
        "%s. Variables: committed defaults from `etl/airflow/.env.example` plus the overrides "
        "listed per scenario. Accepted differences: `etl/tests/golden/%s/%s`."
        % (image_info, script, differences.ACCEPTED_FILE),
        "",
        "**%s: %d checks, %d identical, %d accepted difference, %d failed.**"
        % (
            verdict,
            len(rows),
            totals[differences.IDENTICAL],
            totals[differences.ACCEPTED],
            totals[FAILED],
        ),
        "",
        "| Scenario | Variable overrides | Checks | identical | accepted difference | failed |",
        "|---|---|---|---|---|---|",
    ]
    for case, case_rows, meta in results:
        t = differences.summary(case_rows)
        overrides = (
            ", ".join(
                "`%s=%s`" % (k, airflow_container.variable_value(v))
                for k, v in case.variables.items()
            )
            or "none"
        )
        lines.append(
            "| %s | %s | %d | %d | %d | %d |"
            % (
                case.label,
                overrides,
                len(case_rows),
                t[differences.IDENTICAL],
                t[differences.ACCEPTED],
                t[FAILED],
            )
        )
    lines += ["", "### Checks", "", differences.markdown(rows)]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m harness.parity",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--script", required=True, choices=settings.SCRIPTS)
    parser.add_argument(
        "--dag", help="DAG id (default: the script's entry in parity/dags.yaml)"
    )
    parser.add_argument("--scenario", help="only this committed scenario")
    parser.add_argument(
        "--variant", help="only this flag-on variant from accepted_differences.yaml"
    )
    parser.add_argument(
        "--expect", choices=("identical", "failed"), default="identical"
    )
    args = parser.parse_args(argv)

    entry = resolve_dag(args.script, args.dag)
    selected = cases(args.script, entry, args.scenario, args.variant)
    if not selected:
        print("no scenarios selected", file=sys.stderr)
        return 2

    selection = args.variant or args.scenario or "all"
    out_dir = settings.RUNS_DIR / "parity" / entry.dag_id / args.script / selection
    out_dir.mkdir(parents=True, exist_ok=True)
    infra.wait_ready()
    infra.ensure_resources()
    legacy_image = runner.ensure_image()
    airflow_image = airflow_container.ensure_image()
    (out_dir / "airflow.log").write_text("")
    results = []
    with airflow_container.AirflowContainer(
        airflow_image, out_dir / "airflow.log"
    ) as container:
        image_info = (
            "Airflow image `%s` (`airflow dags test`, %s), legacy image `%s`"
            % (
                airflow_image,
                container.version,
                legacy_image,
            )
        )
        for case in selected:
            print(
                "== %s [dag %s] frozen_time=%s"
                % (case.label, entry.dag_id, case.scn.frozen_time)
            )
            try:
                rows, meta = run_case(case, entry, container, legacy_image, out_dir)
            except (cli.HarnessError, airflow_container.AirflowError) as exc:
                rows, meta = (
                    [
                        Row(
                            case.label,
                            "run",
                            "",
                            "",
                            FAILED,
                            "%s: %s" % (HARNESS_ERROR, exc),
                        )
                    ],
                    {},
                )
            t = differences.summary(rows)
            print(
                "  %d checks: %d identical, %d accepted, %d failed"
                % (len(rows), *t.values())
            )
            results.append((case, rows, meta))

    text = report(args.script, entry, image_info, results)
    (out_dir / "report.md").write_text(text)
    rows = [r for _, case_rows, _ in results for r in case_rows]
    (out_dir / "report.json").write_text(
        json.dumps(
            [
                {
                    "scenario": r.case,
                    "check": r.check,
                    "before": differences.canon(r.before),
                    "after": differences.canon(r.after),
                    "result": r.result,
                    "reason": r.reason,
                }
                for r in rows
            ],
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )
    print()
    print(text)
    print("report: %s" % (out_dir / "report.md").relative_to(settings.REPO_ROOT))
    failed = [r for r in rows if r.result == FAILED]
    harness_errors = [r for r in failed if r.reason.startswith(HARNESS_ERROR)]
    if args.expect == "failed":
        ok = bool(failed) and not harness_errors
        print(
            "expect failed: %s"
            % ("OK, the gate failed as it must" if ok else "NOT MET")
        )
        return 0 if ok else 1
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
