from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest
import sf_attribution as sf
import yaml

WORKLOADS = Path(__file__).resolve().parents[2]


def _load(path):
    return yaml.safe_load(path.read_text())


def _spec(workload):
    return _load(WORKLOADS / workload / "spec.yaml")


def _rounded(value):
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def test_index_covers_endpoints_and_links_matching_specs():
    entries = _load(WORKLOADS / "index.yaml")["workloads"]
    assert len(entries) == len({entry["id"] for entry in entries})
    assert {entry["id"] for entry in entries} == {ep.workload for ep in sf.ENDPOINTS.values()}
    assert {entry["endpoint"] for entry in entries} == set(sf.ENDPOINTS)
    for entry in entries:
        path = WORKLOADS / entry["spec"]
        assert path.is_file(), path
        spec = _load(path)
        ep = sf.ENDPOINTS[entry["endpoint"]]
        assert spec["workload"] == entry["id"] == ep.workload
        assert spec["endpoint"]["csid"] == entry["endpoint"] == sf.csid(ep.workload, ep.endpoint)
        assert spec["endpoint"]["service_user"] == ep.service_user == sf.service_user(ep.csid)


@pytest.mark.parametrize("workload", sorted({ep.workload for ep in sf.ENDPOINTS.values()}))
def test_example_rows_have_exact_ordered_output_columns(workload):
    spec = _spec(workload)
    columns = [column["name"] for column in spec["output"]["columns"]]
    assert len(spec["examples"]["rows"]) == 3
    for row in spec["examples"]["rows"]:
        assert list(row) == columns


def test_usage_examples_follow_business_rule():
    for row in _spec("doc_usage_dashboard")["examples"]["rows"]:
        quota, used = row["quota_bytes"], row["used_bytes"]
        pct = _rounded(Decimal(used) / quota * 100) if quota else None
        band = (
            "no_quota" if not quota else
            "over_quota" if used >= quota else
            "near_limit" if pct >= 80 else "ok"
        )
        assert row["remaining_bytes"] == max(quota - used, 0)
        assert row["usage_pct"] == (float(pct) if pct is not None else None)
        assert row["usage_band"] == band


def test_churn_examples_follow_business_rule():
    statuses = {"101": "active", "102": "active", "103": "suspended"}
    for row in _spec("churn_model")["examples"]["rows"]:
        prior = Decimal(str(row["activity_prior_4wk_avg"]))
        current = row["activity_this_week"]
        drop = (prior - current) / prior * 100 if prior else None
        days = row["days_since_last_login"]
        login = 40 if days >= 30 else 25 if days >= 14 else 10 if days >= 7 else 0
        activity = (
            30 if not prior and not current else
            0 if not prior else
            40 if drop >= 75 else 25 if drop >= 50 else 10 if drop >= 25 else 0
        )
        status = 20 if statuses[row["account_id"][-3:]] == "suspended" else 0
        score = login + activity + status
        assert row["activity_drop_pct"] == (float(_rounded(drop)) if drop is not None else None)
        assert row["login_points"] == login
        assert row["activity_points"] == activity
        assert row["status_points"] == status
        assert row["churn_score"] == score
        assert row["risk_band"] == ("high" if score >= 60 else "medium" if score >= 30 else "low")


def test_search_examples_are_recomputed_from_input_events():
    examples = _spec("doc_search_api")["examples"]
    end = date.fromisoformat(examples["rows"][0]["window_end_date"])
    start = end - timedelta(days=27)
    account = "00000000-0000-4000-8000-000000000101"
    titles = {"03ebe472-1e21-9b1c-20c5-18a0d26cbe6f": "Synthetic document 1"}
    deleted = {"b48e999f-7174-4107-671b-e06d8e9abf30"}
    groups = defaultdict(list)
    for event in examples["input_events"]:
        instant = datetime.fromisoformat(event["occurred_at"].replace("Z", "+00:00"))
        term = " ".join(event["query"].lower().split())
        if not start <= instant.date() <= end or not term:
            continue
        groups[("term", term)].append((instant, event["result_count"]))
        for doc_id in {hit.strip() for hit in event["document_hit_ids"].split(",") if hit.strip()} - deleted:
            groups[("document", doc_id)].append((instant, event["result_count"]))

    rows = []
    for item_type in ("term", "document"):
        items = [(key, events) for (kind, key), events in groups.items() if kind == item_type]
        items.sort(key=lambda item: (-len(item[1]), -max(t.timestamp() for t, _ in item[1]), item[0]))
        for rank, (key, events) in enumerate(items[:10], 1):
            rows.append({
                "window_end_date": end.isoformat(),
                "window_days": 28,
                "account_id": account,
                "item_type": item_type,
                "rank": rank,
                "term": key if item_type == "term" else None,
                "document_id": key if item_type == "document" else None,
                "document_title": titles[key] if item_type == "document" else None,
                "search_count": len(events),
                "zero_result_count": sum(count == 0 for _, count in events) if item_type == "term" else None,
                "last_searched_at": max(t for t, _ in events).strftime("%Y-%m-%d %H:%M:%S"),
            })
    assert examples["rows"] == rows
