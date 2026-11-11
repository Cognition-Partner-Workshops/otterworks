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


def test_databricks_model_mirrors_teradata_model_and_reads_after_schema():
    from semantic import DATABRICKS
    model, views = project(DATABRICKS)
    td_model, td_views = project()
    assert model["explores"] == td_model["explores"]
    assert model["datagroups"] == td_model["datagroups"]
    assert set(views) == set(td_views)
    for view in views.values():
        source = view.get("sql_table_name", view.get("derived_table", {}).get("sql", ""))
        assert "SFX_BILLING" not in source
        assert re.search(r"cpw\.dbx_d1111_after\.billing__[a-z_]+", source), view["name"]
        assert not re.search(r"\b(SEL|ZEROIFNULL|FORMAT|TOP)\b", source)
    for name, sql in queries(DATABRICKS).items():
        assert (ROOT / "contract" / "queries" / "databricks" / f"{name}.sql").read_text().strip() == sql
        assert not re.search(r"\b(SEL|ZEROIFNULL|FORMAT|TOP|1200101)\b", sql)


def test_as_of_pin_rewrites_both_dialects():
    from contract.warehouse import pin_as_of
    assert pin_as_of("x < CURRENT_DATE - 30", "2026-11-09") == "x < DATE '2026-11-09' - 30"
    assert pin_as_of("date_sub(current_date(), 30)", "2026-11-09") == "date_sub(DATE '2026-11-09', 30)"
