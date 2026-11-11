from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import dashboards  # noqa: E402

SPEC = yaml.safe_load(dashboards.SPEC.read_text())
ENTRIES = {e["name"]: e for e in SPEC["workbooks"]}
STORAGE = ENTRIES["Storage Overage"]
LEGACY = dashboards.LEGACY_DIR / STORAGE["file"]
TARGET = dashboards.TARGET_DIR / STORAGE["file"]


class FakeMetabase(dashboards.Metabase):
    """Just enough of the Metabase API, in memory, to check reruns."""

    def __init__(self) -> None:
        super().__init__("http://metabase.test")
        self.objects: dict[str, dict[int, dict[str, Any]]] = {
            "collection": {},
            "database": {},
            "card": {},
            "dashboard": {},
        }
        self.next_id = 1

    def create(self, kind: str, body: dict[str, Any]) -> dict[str, Any]:
        item = {**body, "id": self.next_id}
        if kind == "collection":
            item["location"] = "/"
        self.objects[kind][self.next_id] = item
        self.next_id += 1
        return item

    def call(self, method: str, path: str, body: Any = None) -> Any:
        parts = path.strip("/").split("?")[0].split("/")
        kind = parts[0]
        if method == "GET" and len(parts) == 1:
            return list(self.objects[kind].values())
        if method == "POST" and len(parts) == 1:
            return self.create(kind, body)
        if kind == "card" and parts[-1] == "query":
            return {"row_count": 60}
        if kind == "collection" and parts[-1] == "items":
            model = re.search(r"models=(\w+)", path).group(1)
            owner = int(parts[1])
            return {
                "data": [o for o in self.objects[model].values() if o["collection_id"] == owner]
            }
        item = self.objects[kind][int(parts[1])]
        if method == "PUT":
            if kind == "dashboard":
                for index, dashcard in enumerate(body.get("dashcards", [])):
                    if dashcard["id"] < 0:
                        dashcard["id"] = 1000 + index
            item.update(body)
        return item


@pytest.fixture
def sides():
    return dashboards.sides("sfm-20261110-vk")


def test_storage_overage_is_migrated():
    assert TARGET.exists()


def test_cards_differ_only_in_sql_dialect():
    legacy, target = dashboards.twb.parse(LEGACY), dashboards.twb.parse(TARGET)
    assert [s.name for s in legacy.worksheets] == [s.name for s in target.worksheets]
    for old, new in zip(legacy.worksheets, target.worksheets, strict=True):
        assert (old.mark, old.dimensions, old.measures) == (new.mark, new.dimensions, new.measures)
        assert dashboards.visualization(old) == dashboards.visualization(new)
        old_sql = dashboards.card_sql(old, legacy.datasources[old.datasource].sql)
        new_sql = dashboards.card_sql(new, target.datasources[new.datasource].sql)
        assert "{{business_date}}" in old_sql and "{{business_date}}" in new_sql
        assert "mart.mart_overage_charges" in old_sql
        assert "MARTS.BUILD_MART_OVERAGE" in new_sql
        normalise = {"mart.mart_overage_charges": "T", "MARTS.BUILD_MART_OVERAGE": "T"}
        normalise |= {"COUNT_BIG(*)": "COUNT(*)"}
        for text, same in normalise.items():
            old_sql, new_sql = old_sql.replace(text, same), new_sql.replace(text, same)
        assert old_sql == new_sql


def test_bar_cards_sort_by_measure_and_tables_by_dimensions():
    workbook = dashboards.twb.parse(LEGACY)
    sheets = {s.name: s for s in workbook.worksheets}
    bar = sheets["Overage Revenue by Tenant"]
    table = sheets["Storage vs Included"]
    assert dashboards.card_sql(bar, workbook.datasources[bar.datasource].sql).endswith(
        "ORDER BY 2 DESC, 1"
    )
    assert dashboards.card_sql(table, workbook.datasources[table.datasource].sql).endswith(
        "ORDER BY 1, 2"
    )


def test_strip_order_keeps_top_queries():
    assert dashboards.strip_order("SELECT a FROM t ORDER BY a DESC") == "SELECT a FROM t"
    top = "SELECT TOP (20) a FROM t ORDER BY a DESC"
    assert dashboards.strip_order(top) == top


def test_reflow_pushes_cards_below_a_card_that_grew():
    cards = [
        {"row": 1, "col": 0, "size_x": 24, "size_y": 33},
        {"row": 10, "col": 0, "size_x": 12, "size_y": 8},
        {"row": 10, "col": 12, "size_x": 12, "size_y": 8},
    ]
    dashboards.reflow(cards)
    assert [c["row"] for c in cards] == [1, 34, 34]


def test_rerun_updates_in_place(sides):
    sqlserver, snowflake = sides
    mb = FakeMetabase()
    first = [
        dashboards.build_dashboard(mb, side, STORAGE, path, "2026-09-30")
        for side, path in ((sqlserver, LEGACY), (snowflake, TARGET))
    ]
    snapshot = {kind: sorted(objects) for kind, objects in mb.objects.items()}
    second = [
        dashboards.build_dashboard(mb, side, STORAGE, path, "2026-09-30")
        for side, path in ((sqlserver, LEGACY), (snowflake, TARGET))
    ]
    assert first == second
    assert {kind: sorted(objects) for kind, objects in mb.objects.items()} == snapshot
    collections = {c["name"]: c["id"] for c in mb.objects["collection"].values()}
    assert set(collections) == {"SQL Server", "Snowflake"}
    for name, collection in collections.items():
        cards = [c for c in mb.objects["card"].values() if c["collection_id"] == collection]
        assert [c["name"] for c in cards] == [
            "Storage Overage: Overage Revenue by Tenant",
            "Storage Overage: Overage GB by Plan Tier",
            "Storage Overage: Storage vs Included",
        ], name


def test_dashboards_match_apart_from_the_connection(sides):
    mb = FakeMetabase()
    built = [
        mb.objects["dashboard"][dashboards.build_dashboard(mb, side, STORAGE, path, "2026-09-30")]
        for side, path in zip(sides, (LEGACY, TARGET), strict=True)
    ]
    layouts = [
        [(d["row"], d["col"], d["size_x"], d["size_y"]) for d in board["dashcards"]]
        for board in built
    ]
    assert layouts[0] == layouts[1]
    assert built[0]["parameters"] == built[1]["parameters"]
    databases = {d["name"]: d for d in mb.objects["database"].values()}
    assert databases["UBW Snowflake (sfm-20261110-vk)"]["details"]["role"] == (
        "OW_UBW_SFM_20261110_VK_READER"
    )


@pytest.mark.parametrize("entry", SPEC["workbooks"], ids=lambda e: e["name"])
def test_every_legacy_workbook_builds(entry, sides):
    mb = FakeMetabase()
    board = dashboards.build_dashboard(
        mb, sides[0], entry, dashboards.LEGACY_DIR / entry["file"], "2026-09-30"
    )
    workbook = dashboards.twb.parse(dashboards.LEGACY_DIR / entry["file"])
    assert len(mb.objects["dashboard"][board]["dashcards"]) == len(workbook.worksheets) + 1
