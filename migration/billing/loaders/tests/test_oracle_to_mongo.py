"""Unit tests for migration/billing/loaders/oracle_to_mongo.py (run: pytest migration/billing/loaders/tests -q).

The loader maps rows through recon.load_documents, so these tests pin the loader's own
behaviour: which tables a run reads, how embedded / quarantine collections are validated and
grouped, upsert-by-_id statistics, and that deferred indexes are never built.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "recon" / "tests"))
sys.path.insert(0, str(HERE.parent))
import oracle_to_mongo as loader  # noqa: E402
import recon  # noqa: E402
from test_recon import small_estate  # noqa: E402

NOW = dt.datetime(2026, 10, 2, 0, 0, tzinfo=dt.timezone.utc)
U4 = loader.U4_COLLECTIONS


@pytest.fixture(scope="module")
def inputs() -> recon.Inputs:
    return recon.build_inputs(fixture_path=None)


@pytest.fixture(scope="module")
def estate(inputs):
    return small_estate(inputs)


class FakeSource:
    def __init__(self, tables):
        self.tables, self.reads = tables, []

    def rows(self, table):
        self.reads.append(table)
        return list(self.tables.get(table, []))


class FakeResult:
    def __init__(self, upserted, matched, modified):
        self.upserted_count, self.matched_count, self.modified_count = upserted, matched, modified


class FakeCollection:
    def __init__(self):
        self.docs, self.indexes = {}, []

    def bulk_write(self, ops, ordered=False):
        upserted = matched = modified = 0
        for op in ops:
            key = op._filter["_id"]
            if key in self.docs:
                matched += 1
                if self.docs[key] != op._doc:
                    modified += 1
            else:
                upserted += 1
            self.docs[key] = op._doc
        return FakeResult(upserted, matched, modified)

    def count_documents(self, _filter):
        return len(self.docs)

    def create_index(self, keys, name, **options):
        self.indexes.append((name, keys, options))


class FakeDb(dict):
    def __missing__(self, name):
        self[name] = FakeCollection()
        return self[name]


def test_u4_collection_set_is_the_mapping_spec_set(inputs):
    names = {c.name for c in inputs.collections}
    assert set(U4) <= names
    maps = loader._collection_maps(inputs, U4)
    assert [m.name for m in maps] == U4
    feed = next(m for m in maps if m.name == "invoice_feed")
    assert [e.path for e in feed.embedded] == ["lines"] and feed.embedded[0].quarantine_collection == "invoice_feed_quarantine"
    assert next(m for m in maps if m.name == "invoice_feed_quarantine").quarantine_of is feed.embedded[0]


def test_quarantine_and_its_parent_must_be_loaded_together(inputs):
    with pytest.raises(SystemExit, match="quarantines the orphans of invoice_feed"):
        loader._collection_maps(inputs, ["invoice_feed_quarantine"])
    with pytest.raises(SystemExit, match="sends orphans to invoice_feed_quarantine"):
        loader._collection_maps(inputs, ["invoice_feed"])
    with pytest.raises(SystemExit, match="not in mapping_spec.json"):
        loader._collection_maps(inputs, ["invoices", "nope"])
    assert [m.name for m in loader._collection_maps(inputs, ["invoices", "credit_notes"])] == ["invoices", "credit_notes"]


def test_read_tables_reads_primary_and_child_tables_once(inputs, estate):
    tables, _ = estate
    source = FakeSource(tables)
    read = loader.read_tables(source, loader._collection_maps(inputs, U4))
    assert set(read) == {"CREDIT_NOTES", "INVOICE_HEADER", "INVOICE_LINE", "INVOICES", "INVOICE_LINES"}
    assert sorted(source.reads) == sorted(set(source.reads)), "every source table is read exactly once"


def test_map_documents_matches_recon_reference_mapping(inputs, estate):
    tables, expected = estate
    maps = loader._collection_maps(inputs, U4)
    docs = loader.map_documents(inputs, maps, tables, NOW)
    assert set(docs) == set(U4)
    for name in U4:
        assert docs[name] == expected[name], name
    headers = {d["_id"] for d in docs["invoice_feed"]}
    assert docs["invoice_feed_quarantine"] and all(q["invoiceId"] not in headers for q in docs["invoice_feed_quarantine"])
    assert all(q["quarantine"]["reason"] == "orphaned_rows" for q in docs["invoice_feed_quarantine"])
    embedded = sum(len(d.get("lines", [])) for d in docs["invoice_feed"])
    assert embedded + len(docs["invoice_feed_quarantine"]) == len(tables["INVOICE_LINE"])
    assert sum(len(d.get("lines", [])) for d in docs["invoices"]) == len(tables["INVOICE_LINES"])


def test_load_collection_upserts_by_id_and_rerun_is_noop(inputs, estate):
    tables, _ = estate
    maps = loader._collection_maps(inputs, U4)
    docs = loader.map_documents(inputs, maps, tables, NOW)
    db = FakeDb()
    first = {m.name: loader.load_collection(db, m, docs[m.name], tables) for m in maps}
    second = {m.name: loader.load_collection(db, m, docs[m.name], tables) for m in maps}
    for name in U4:
        assert first[name]["upserted"] == len(docs[name]) == first[name]["target_count_after"]
        assert (second[name]["upserted"], second[name]["modified"]) == (0, 0)
        assert second[name]["matched"] == len(docs[name])
    assert first["invoice_feed"]["embedded"]["lines"]["table"] == "INVOICE_LINE"
    assert first["invoice_feed"]["embedded"]["lines"]["embedded_rows"] + first["invoice_feed_quarantine"]["documents"] == len(tables["INVOICE_LINE"])
    assert first["invoice_feed_quarantine"]["quarantine_of"] == "INVOICE_LINE"


def test_ensure_indexes_skips_deferred_builds(inputs):
    db = FakeDb()
    created = loader.ensure_indexes(inputs.spec, db, U4)
    names = {(c["collection"], c["name"]) for c in created}
    assert ("invoice_feed", "ix_invoice_feed_status_due") not in names
    assert {("invoices", "ix_invoices_tenant_issued"), ("invoices", "uq_invoices_lines_id"),
            ("credit_notes", "ix_credit_notes_tenant_issued"), ("invoice_feed", "ix_invoice_feed_batch"),
            ("invoice_feed", "uq_invoice_feed_lines_line_id"),
            ("invoice_feed_quarantine", "ix_invoice_feed_quarantine_invoice")} <= names
    assert all("build" not in options for _name, _keys, options in db["invoice_feed"].indexes)
