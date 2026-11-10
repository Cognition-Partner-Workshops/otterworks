import re
import lkml

from semantic import ROOT, project, queries


def test_every_lookml_file_parses_and_views_read_billing_schema():
    for path in ROOT.rglob("*.lkml"):
        assert lkml.load(path.read_text())
    _, views = project()
    assert views
    for view in views.values():
        source = view.get("sql_table_name", view.get("derived_table", {}).get("sql", ""))
        assert re.search(r"SFX_BILLING\.[A-Z_]+", source), view["name"]


def test_explores_and_join_fields_resolve():
    model, views = project()
    for explore in model["explores"]:
        assert explore["name"] in views
        available = {explore["name"]} | {j["name"] for j in explore.get("joins", [])}
        for join in explore.get("joins", []):
            assert join["name"] in views
            assert join["relationship"] == "many_to_one"
            for owner, field in re.findall(r"\$\{(\w+)\.(\w+)\}", join["sql_on"]):
                assert owner in available
                assert field in {d["name"] for d in views[owner]["dimensions"]}


def test_pdt_refresh_and_feature_access():
    model, views = project()
    assert model["datagroups"][0]["max_cache_age"] == "4 hours"
    assert model["datagroups"][0]["interval_trigger"] == "4 hours"
    assert views["overdue_accounts"]["derived_table"]["datagroup_trigger"] == "finance_four_hours"
    assert all(e["required_access_grants"] == ["finance_enabled"] for e in model["explores"])


def test_checked_in_queries_match_selected_lookml_fields():
    for name, sql in queries().items():
        assert (ROOT / "contract" / "queries" / f"{name}.sql").read_text().strip() == sql
