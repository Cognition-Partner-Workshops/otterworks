"""Build an offline consumption ledger from Snowflake history exports.

No connection or credentials are needed. Missing values remain pending; observed
query subtotals must not be confused with reconciled warehouse billing totals.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from decimal import Decimal
from pathlib import Path
from typing import Any

import sf_attribution as sf

PENDING = sf.PENDING
COMMENT = re.compile(r"/\*\s*(\{[^*]*\})\s*\*/\s*$", re.DOTALL)


def rows(values: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [{k.lower(): v for k, v in row.items()} for row in values]


def json_object(value: Any) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def query_identity(query: Mapping[str, Any], run_token: str) -> tuple[dict[str, Any], str] | None:
    raw = query.get("query_tag", "")
    tag = json_object(raw)
    source = "query_tag"
    if not tag and isinstance(raw, str):
        try:
            parsed, end = json.JSONDecoder().raw_decode(raw)
            if isinstance(parsed, dict) and raw[end:].startswith(";schemachange "):
                tag, source = parsed, "query_tag_schemachange_suffix"
        except ValueError:
            pass
    if not tag.get("csid") and tag.get("StreamlitEngine") == "ExecuteStreamlit":
        match = COMMENT.search(query.get("query_text") or "")
        if not match:
            return None
        try:
            tag = sf.parse_query_tag(match[1])
        except sf.AttributionError:
            return None
        if tag["phase"] != "runtime":
            return None
        source = "verified_streamlit_json_comment_fallback"
    if not all(isinstance(tag.get(k), str) and tag[k] for k in sf.QUERY_TAG_KEYS):
        return None
    run_id = tag["run_id"]
    if run_id != run_token and not run_id.startswith(run_token + "-"):
        return None
    if not sf.CSID_RE.fullmatch(tag["csid"]) or tag["phase"] not in sf.PHASES:
        return None
    return tag, source


def amount(value: Any) -> str:
    return PENDING if value is None or value == PENDING else str(Decimal(str(value)))


def subtotal(values: Iterable[Any]) -> str:
    known = [Decimal(str(v)) for v in values if v is not None and v != PENDING]
    return str(sum(known, Decimal(0))) if known else PENDING


def build_ledger(
    exports: Mapping[str, list[dict[str, Any]]],
    registrations: Mapping[str, dict[str, Any]] | None = None,
    *,
    run_token: str = sf.RUN_TOKEN,
) -> dict[str, Any]:
    registry = {csid: {"workload": ep.workload} for csid, ep in sf.ENDPOINTS.items()}
    registry.update(registrations or {})
    queries: dict[str, dict[str, Any]] = {}
    for name in ("query_history", "recent_queries"):
        for query in rows(exports.get(name, [])):
            queries.setdefault(query["query_id"], query)
    attributed = {r["query_id"]: r for r in rows(exports.get("attribution", []))}
    tasks = {r["query_id"]: r for r in rows(exports.get("tasks", [])) if r.get("query_id")}
    cortex: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for usage in rows(exports.get("cortex", [])):
        cortex[usage["query_id"]].append(usage)
    timeline = []
    by_csid: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for query_id, query in queries.items():
        identity = query_identity(query, run_token)
        if identity is None:
            continue
        tag, source = identity
        compute = attributed.get(query_id, {})
        ai = cortex.get(query_id, [])
        event = {k: tag[k] for k in sf.QUERY_TAG_KEYS}
        event.update(
            query_id=query_id, tag_source=source,
            session_url=tag.get("session_url", tag.get("session", PENDING)),
            task_execution_id=tasks.get(query_id, {}).get("graph_run_group_id") or PENDING,
            compute_credits=amount(compute.get("credits_attributed_compute")),
            query_acceleration_credits=amount(compute.get("credits_used_query_acceleration")),
            cortex_credits=subtotal(r.get("token_credits") for r in ai),
            cortex_tokens=subtotal(r.get("tokens") for r in ai),
            cloud_services_credits=amount(query.get("credits_used_cloud_services")),
            attribution_limitations="operator/control commit=none" if tag["commit"] == "none" else "",
        )
        for key in ("start_time", "end_time", "user_name", "role_name", "warehouse_name", "execution_status"):
            event[key] = query.get(key)
        by_csid[tag["csid"]].append(event)
        timeline.append(event)
    ledger = []
    for csid in sorted(set(registry) | set(by_csid)):
        events = by_csid[csid]
        entry = {"csid": csid, "registration": registry.get(csid, {"status": "observed only"}),
                 "query_count": len(events), "system_query_count": sum(e["user_name"] == "SYSTEM" for e in events)}
        for phase in sf.PHASES:
            phase_events = [e for e in events if e["phase"] == phase]
            entry[phase] = {
                "compute_observed_credits": subtotal(e["compute_credits"] for e in phase_events),
                "compute_total_credits": PENDING,
                "pending_query_count": sum(e["compute_credits"] == PENDING for e in phase_events),
                "query_acceleration_observed_credits": subtotal(e["query_acceleration_credits"] for e in phase_events),
                "cloud_services_observed_credits": subtotal(e["cloud_services_credits"] for e in phase_events),
                "cortex_observed_credits": subtotal(e["cortex_credits"] for e in phase_events),
                "cortex_total_credits": PENDING,
                "cortex_observed_tokens": subtotal(e["cortex_tokens"] for e in phase_events),
            }
        entry.update(
            run_ids=sorted({e["run_id"] for e in events}), commits=sorted({e["commit"] for e in events}),
            session_urls=sorted({e["session_url"] for e in events if e["session_url"] != PENDING}),
            acu=PENDING, acu_allocation="session costs remain separate; no per-CSID allocation",
            pending_account_usage=True,
        )
        ledger.append(entry)
    metering = rows(exports.get("metering", []))
    reconciliation = []
    for warehouse in sorted({r["warehouse_name"] for r in metering}):
        measured = [r for r in metering if r["warehouse_name"] == warehouse]
        all_attributed = [r for r in attributed.values() if r.get("warehouse_name") == warehouse]
        total = subtotal(r.get("credits_used_compute") for r in measured)
        known = subtotal(r.get("credits_attributed_compute") for r in all_attributed)
        reconciliation.append({
            "warehouse_name": warehouse, "metered_compute_credits": total,
            "metered_cloud_services_credits": subtotal(r.get("credits_used_cloud_services") for r in measured),
            "all_query_compute_observed_credits": known,
            "unreconciled_difference_credits": str(Decimal(total) - Decimal(known))
            if total != PENDING and known != PENDING else PENDING,
            "startup_idle_unrelated_credits": PENDING, "recent_unmetered_credits": PENDING,
            "status": "pending attribution lag; difference is not an idle estimate",
        })
    coverage = {}
    for name, data in exports.items():
        normalized = rows(data)
        times = [str(r.get("end_time") or r.get("completed_time")) for r in normalized
                 if r.get("end_time") or r.get("completed_time")]
        coverage[name] = {"row_count": len(data), "latest_observed_end_time": max(times) if times else PENDING,
                          "completeness": PENDING}
    return {
        "run_token": run_token, "application": sf.APPLICATION,
        "application_registration": sf.APPLICATION_REGISTRATION,
        "coverage": coverage, "ledger": ledger,
        "timeline": sorted(timeline, key=lambda e: str(e.get("start_time"))),
        "warehouse_reconciliation": reconciliation,
        "session_costs": exports.get("session_costs", []),
    }


def write_csv(path: Path, records: list[dict[str, Any]]) -> None:
    if not records:
        path.write_text("")
        return
    fields = list(dict.fromkeys(k for record in records for k in record))
    with path.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for record in records:
            writer.writerow({k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in record.items()})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--registrations", type=Path)
    parser.add_argument("--run-token", default=sf.RUN_TOKEN)
    args = parser.parse_args()
    names = ("query_history", "recent_queries", "attribution", "tasks", "cortex", "metering", "session_costs")
    exports = {name: json.loads((args.input_dir / f"{name}.json").read_text()) for name in names
               if (args.input_dir / f"{name}.json").exists()}
    registry = json.loads(args.registrations.read_text()) if args.registrations else None
    result = build_ledger(exports, registry, run_token=args.run_token)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "ledger.json").write_text(json.dumps(result, indent=2))
    for name in ("ledger", "timeline", "warehouse_reconciliation", "session_costs"):
        write_csv(args.output_dir / f"{name}.csv", result[name])


if __name__ == "__main__":
    main()
