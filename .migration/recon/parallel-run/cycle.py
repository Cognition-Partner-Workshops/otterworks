"""One "production cycle" of the coexistence window: replay every write scenario under
procs/scenarios/ (kind: procedure) against the LEGACY stack of a disposable procs namespace,
through the legacy Flask app's HTTP routes (services/legacy-billing/app/app.py), in scenario
order and without resetting the schema between calls. The fixture is the only source of change;
the delta sync (services/billing-service/app/delta.py) is run after each cycle.

The scenarios are date-anchored business events (plan change effective 2026-03-01, February
rating and invoicing, dunning as of a fixed date) and `sp_change_plan` is not re-runnable on the
same date (its subscription id is md5(tenant, plan, effective_on)), so cycle N replays them as the
next production period: every `date` input is shifted forward by N-1 months (`--shift-months`).

HTTP only: this script opens no database connection (the dbx guard cannot resolve a run-time
CALL to a procs namespace, wave-3 finding V8) and never touches the billing_ro source fixture
`billing_mig`, Atlas, or the committed transcripts.

    NS=p5 python3 .migration/recon/parallel-run/cycle.py --out .migration/recon/parallel-run/cycle-1/cycle.json
"""
import argparse, calendar, json, os, sys, time, urllib.error, urllib.parse, urllib.request, zlib
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
# legacy entrypoint -> (route template, body encoding, body input names)
ROUTES = {
    "billing.sp_change_plan": ("/plans/{tenant_id}/change", "form", ("plan_id", "effective_on")),
    "billing.sp_finalize_rating": ("/api/rating/finalize", "json", ("tenant_id", "period_start", "period_end")),
    "billing.sp_issue_invoice": ("/api/invoices/{tenant_id}/issue", "form", ("period_start", "period_end")),
    "billing.sp_schedule_dunning": ("/api/dunning/schedule", "form", ("as_of",)),
    "billing.sp_suspend_overdue": ("/api/dunning/suspend", "form", ("as_of",)),
}


def scenarios():
    for path in sorted((ROOT / "procs" / "scenarios").glob("*/*.yaml")):
        doc = yaml.safe_load(path.read_text())
        if doc.get("kind") == "procedure":
            yield path.relative_to(ROOT).as_posix(), doc


def shift_months(day, months):
    """Day-preserving shift; a last-day-of-month input stays the last day (Feb 28 -> Mar 31)."""
    month = day.month - 1 + months
    year, month = day.year + month // 12, month % 12 + 1
    last = calendar.monthrange(year, month)[1]
    end_of_month = day.day == calendar.monthrange(day.year, day.month)[1]
    return day.replace(year=year, month=month, day=last if end_of_month else min(day.day, last))


def call(base, scenario, months):
    template, encoding, body_names = ROUTES[scenario["entrypoint"]]
    inputs = {
        item["name"]: str(shift_months(item["value"], months) if item["type"] == "date" else item["value"])
        for item in scenario["inputs"]
    }
    path = template.format(**inputs)
    body = {name: inputs[name] for name in body_names}
    if encoding == "json":
        data, content_type = json.dumps(body).encode(), "application/json"
    else:
        data, content_type = urllib.parse.urlencode(body).encode(), "application/x-www-form-urlencoded"
    request = urllib.request.Request(base + path, data=data, method="POST", headers={"Content-Type": content_type})
    opener = urllib.request.build_opener(_NoRedirect)
    started = time.monotonic()
    try:
        with opener.open(request, timeout=15) as response:
            status = response.status
    except urllib.error.HTTPError as error:
        status = error.code
    return {"path": path, "inputs": inputs, "status": status, "duration_ms": round((time.monotonic() - started) * 1000)}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ARG002
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ns", default=os.environ.get("NS", "p5"))
    parser.add_argument("--cycle", type=int, required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--shift-months", type=int, help="months added to every date input (default: cycle-1)")
    args = parser.parse_args()
    months = args.shift_months if args.shift_months is not None else args.cycle - 1
    port = 8096 + zlib.crc32(args.ns.encode()) % 1000
    base = f"http://127.0.0.1:{port}"
    with urllib.request.urlopen(base + "/health", timeout=15) as response:
        assert json.loads(response.read())["status"] == "UP"
    calls = []
    for source, scenario in scenarios():
        result = call(base, scenario, months)
        calls.append({"scenario": scenario["id"], "source": source, "entrypoint": scenario["entrypoint"], **result})
        print(f"{scenario['id']:<12} {scenario['entrypoint']:<28} -> {result['status']}")
    ok = all(call_["status"] in (200, 302) for call_ in calls)
    out = {
        "cycle": args.cycle,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "namespace": args.ns,
        "legacy_app": base,
        "date_inputs_shifted_months": months,
        "scenarios_replayed": len(calls),
        "all_succeeded": ok,
        "calls": calls,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2) + "\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
