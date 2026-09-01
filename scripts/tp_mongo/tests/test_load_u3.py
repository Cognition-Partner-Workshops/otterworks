from datetime import datetime, timezone
from pathlib import Path
import sys
import uuid

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
import load_u3


def _row(**overrides):
    row = {
        "id": uuid.UUID("AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA"),
        "title": "Title",
        "content": "Content",
        "content_type": "text/plain",
        "owner_id": uuid.UUID("BBBBBBBB-BBBB-BBBB-BBBB-BBBBBBBBBBBB"),
        "folder_id": uuid.UUID("CCCCCCCC-CCCC-CCCC-CCCC-CCCCCCCCCCCC"),
        "is_deleted": False,
        "is_template": True,
        "word_count": 3,
        "version": 0,
        "created_at": datetime(2026, 9, 1, 12, 0, 0, 123456, timezone.utc),
        "updated_at": datetime(
            2026, 9, 1, 12, 0, 1, 987654, timezone.utc
        ),
    }
    row.update(overrides)
    return row


def _version(number, identifier):
    return {
        "id": uuid.UUID(identifier),
        "document_id": uuid.UUID("AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA"),
        "version_number": number,
        "title": f"Version {number}",
        "content": f"Content {number}",
        "created_by": uuid.UUID("DDDDDDDD-DDDD-DDDD-DDDD-DDDDDDDDDDDD"),
        "created_at": datetime(
            2026, 9, 1, 12, 0, number, 123999, timezone.utc
        ),
    }


def test_transform_document_normalizes_uuids_omits_null_folder_and_truncates_ms():
    document = load_u3.transform_document(_row(folder_id=None))

    assert document["_id"] == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    assert document["owner_id"] == "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    assert "folder_id" not in document
    assert document["created_at"] == datetime(
        2026, 9, 1, 12, 0, 0, 123000, timezone.utc
    )
    assert document["updated_at"] == datetime(
        2026, 9, 1, 12, 0, 1, 987000, timezone.utc
    )


def test_transform_document_sorts_versions_and_computes_gaps():
    versions = [
        _version(7, "77777777-7777-7777-7777-777777777777"),
        _version(1, "11111111-1111-1111-1111-111111111111"),
        _version(4, "44444444-4444-4444-4444-444444444444"),
        _version(2, "22222222-2222-2222-2222-222222222222"),
    ]

    document = load_u3.transform_document(_row(), versions)

    assert [version["version_number"] for version in document["versions"]] == [
        1,
        2,
        4,
        7,
    ]
    assert document["version_gaps"] == [3, 5, 6]


def test_transform_document_reports_trailing_declared_version_gap():
    versions = [_version(1, "11111111-1111-1111-1111-111111111111"),
                _version(2, "22222222-2222-2222-2222-222222222222")]

    document = load_u3.transform_document(_row(version=3), versions)

    assert document["version_gaps"] == [3]


def test_transform_document_without_versions_has_no_gaps():
    assert load_u3.transform_document(_row())["version_gaps"] == []


def test_transform_snapshot_omits_null_label_and_preserves_state_b64():
    snapshot = load_u3.transform_snapshot(
        {
            "id": uuid.UUID("EEEEEEEE-EEEE-EEEE-EEEE-EEEEEEEEEEEE"),
            "document_id": uuid.UUID("AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA"),
            "state_b64": "QUJDRA==",
            "label": None,
            "created_by": uuid.UUID("DDDDDDDD-DDDD-DDDD-DDDD-DDDDDDDDDDDD"),
            "created_at": datetime(
                2026, 9, 1, 12, 0, 0, 456789, timezone.utc
            ),
        }
    )

    assert snapshot["state_b64"] == "QUJDRA=="
    assert "label" not in snapshot
    assert snapshot["document_id"] == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


def test_orphan_snapshot_quarantine_shape():
    snapshot = load_u3.transform_snapshot(
        {
            "id": uuid.UUID("EEEEEEEE-EEEE-EEEE-EEEE-EEEEEEEEEEEE"),
            "document_id": uuid.UUID("FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF"),
            "state_b64": "state",
            "label": "orphan",
            "created_by": uuid.UUID("DDDDDDDD-DDDD-DDDD-DDDD-DDDDDDDDDDDD"),
            "created_at": datetime(2026, 9, 1, tzinfo=timezone.utc),
        }
    )

    quarantined = load_u3.quarantine_snapshot(snapshot)
    assert quarantined["reason_class"] == "orphan_parent"
    assert quarantined["unit"] == "U3"
    assert quarantined["ns"] == load_u3.NS_VALUE
    assert quarantined["source_key"] == {"id": snapshot["_id"]}
    assert "ns" not in quarantined["row"]


def test_target_db_guard_rejects_other_databases():
    with pytest.raises(ValueError):
        load_u3.validate_target_db("other-db")


def test_owned_collection_names_are_exact():
    assert load_u3.UNIT_COLLECTIONS == ("documents", "document_snapshots")
    assert load_u3.QUARANTINE_COLLECTIONS == ("orphan_document_snapshots",)
