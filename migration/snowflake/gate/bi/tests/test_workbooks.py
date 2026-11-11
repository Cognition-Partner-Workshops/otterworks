from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml

BI = Path(__file__).resolve().parents[1]
ROOT = BI.parents[1]
sys.path[:0] = [str(BI), str(BI.parent)]

import parity  # noqa: E402
import twb  # noqa: E402

SPEC = yaml.safe_load((BI / "workbooks.yaml").read_text())
LEGACY = ROOT / "source" / "tableau"
REPORTS = ROOT / "source" / "reports"
UNITS = {row["unit"] for row in yaml.safe_load((BI.parent / "manifest.yaml").read_text())["units"]}


def test_estate_has_twenty_workbooks():
    assert len(SPEC["workbooks"]) == 20
    assert sorted(p.name for p in LEGACY.glob("*.twb")) == sorted(
        w["file"] for w in SPEC["workbooks"]
    )


@pytest.mark.parametrize("entry", SPEC["workbooks"], ids=lambda e: e["name"])
def test_workbook_matches_contract(entry):
    workbook = twb.parse(LEGACY / entry["file"])
    assert workbook.dashboards and workbook.worksheets
    assert "Business Date" in workbook.parameters
    for spec in entry["datasources"]:
        ds = workbook.by_caption(spec["caption"])
        assert ds is not None, spec["caption"]
        assert ds.connection_class == "sqlserver"
        assert (REPORTS / f"{spec['report']}.rdl").exists()
        assert spec["keys"] and set(spec["keys"]) <= set(ds.columns)
        assert "<[Parameters].[Business Date]>" in ds.sql
        assert "password" not in ds.connection
    assert set(entry["units"]) <= UNITS
    for sheet in workbook.worksheets:
        assert sheet.datasource in workbook.datasources
        assert sheet.dimensions and sheet.measures


def test_storage_overage_lineage():
    entry = next(w for w in SPEC["workbooks"] if w["name"] == "Storage Overage")
    assert {"rollup_storage_daily", "rate_overage", "build_mart_overage"} <= set(entry["units"])
    assert [d["report"] for d in entry["datasources"]] == [
        "rpt_overage_charges",
        "rpt_overage_by_tier",
        "rpt_storage_vs_included",
    ]


def test_bind_quotes_parameters():
    assert twb.bind("x = <[Parameters].[Plan Tier]>", {"Plan Tier": "o'k"}) == "x = 'o''k'"


def test_compare_flags_integer_division():
    legacy = pd.DataFrame({"tenant_id": ["a", "b"], "overage_gb": [40, 0]})
    naive = pd.DataFrame({"TENANT_ID": ["a", "b"], "OVERAGE_GB": [40.638672, 0]})
    result = parity.compare_datasource(legacy, naive, ["tenant_id"], {})
    assert result["status"] == "DIVERGE" and result["differing_keys"] == 1
    assert result["diffs"][0]["sqlserver"] == 40
    fixed = parity.compare_datasource(legacy, naive.assign(OVERAGE_GB=[40, 0]), ["tenant_id"], {})
    assert fixed["status"] == "PASS"


def test_compare_reports_missing_rows_and_columns():
    legacy = pd.DataFrame({"k": [1, 2], "v": [1, 2]})
    assert parity.compare_datasource(legacy, legacy.iloc[:1], ["k"], {})["differing_keys"] == 1
    assert parity.compare_datasource(legacy, legacy[["k"]], ["k"], {})["status"] == "DIVERGE"
