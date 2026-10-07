import pytest

from harness import differences as d
from harness.differences import ABSENT, ACCEPTED, FAILED, IDENTICAL, Accepted

GOLDEN = {
    "result.json": {"exit_code": 0},
    "s3.json": {
        "lake": {"reports/r.json": {"body": {"count": 1, "ok": True}, "format": "json"}},
        "empty": {},
    },
    "dynamodb.json": {
        "events": {
            "key_schema": ["id"],
            "items": [{"id": {"S": "e1"}, "n": {"N": "1"}}, {"id": {"S": "e2"}}],
        }
    },
    "sqs.json": {"q": {"visible": 0, "in_flight": 0}},
    "postgres.json": {"t": {"columns": [{"name": "a", "type": "text"}], "rows": []}},
    "meilisearch.json": {
        "docs": {
            "primary_key": "id",
            "settings": {},
            "stats": {"numberOfDocuments": 1},
            "documents": [{"id": "d1", "title": "x"}],
        }
    },
}


def copy(value):
    import json

    return json.loads(json.dumps(value))


def by_check(rows):
    return {r.check: r for r in rows}


def test_one_check_per_compared_thing():
    assert list(d.checks(GOLDEN)) == [
        "result.json exit_code",
        "s3.json s3://lake/",
        "s3.json s3://lake/reports/r.json",
        "s3.json s3://empty/",
        "dynamodb.json events key_schema",
        "dynamodb.json events[id=e1]",
        "dynamodb.json events[id=e2]",
        "sqs.json q",
        "postgres.json t columns",
        "postgres.json t rows",
        "meilisearch.json docs primary_key",
        "meilisearch.json docs settings",
        "meilisearch.json docs stats",
        'meilisearch.json docs[id="d1"]',
    ]


def test_identical_snapshot_is_all_identical():
    rows = d.classify("s/x", GOLDEN, copy(GOLDEN))
    assert {r.result for r in rows} == {IDENTICAL}
    assert len(rows) == len(d.checks(GOLDEN))


def test_any_unlisted_difference_fails_and_extra_or_missing_checks_count():
    actual = copy(GOLDEN)
    actual["s3.json"]["lake"]["reports/r.json"]["body"]["count"] = 2
    actual["s3.json"]["lake"]["stray"] = {"body": "", "format": "text"}
    actual["dynamodb.json"]["events"]["items"].pop()
    actual["result.json"]["exit_code"] = 1
    rows = by_check(d.classify("s/x", GOLDEN, actual))
    for check in (
        "s3.json s3://lake/reports/r.json",
        "s3.json s3://lake/stray",
        "dynamodb.json events[id=e2]",
        "result.json exit_code",
    ):
        assert rows[check].result == FAILED, check
        assert rows[check].reason == "not an accepted difference"
    assert rows["s3.json s3://lake/stray"].before is ABSENT
    assert rows["dynamodb.json events[id=e2]"].after is ABSENT
    assert rows["sqs.json q"].result == IDENTICAL


def test_numeric_type_and_float_differences_are_not_rounded_up():
    actual = copy(GOLDEN)
    actual["s3.json"]["lake"]["reports/r.json"]["body"]["count"] = 1.0
    rows = by_check(d.classify("s/x", GOLDEN, actual))
    assert rows["s3.json s3://lake/reports/r.json"].result == FAILED


def test_accepted_difference_needs_the_exact_before_and_after():
    check = "dynamodb.json events[id=e1]"
    before = GOLDEN["dynamodb.json"]["events"]["items"][0]
    accepted = (Accepted(check, before, ABSENT, "deleted on purpose"),)
    deleted = copy(GOLDEN)
    deleted["dynamodb.json"]["events"]["items"].pop(0)
    row = by_check(d.classify("s/x", GOLDEN, deleted, accepted))[check]
    assert (row.result, row.reason) == (ACCEPTED, "deleted on purpose")

    changed = copy(GOLDEN)
    changed["dynamodb.json"]["events"]["items"][0]["n"] = {"N": "2"}
    row = by_check(d.classify("s/x", GOLDEN, changed, accepted))[check]
    assert row.result == FAILED and "after value" in row.reason

    row = by_check(d.classify("s/x", GOLDEN, copy(GOLDEN), accepted))[check]
    assert row.result == FAILED and "did not occur" in row.reason


def test_accepted_difference_with_wrong_before_or_unknown_check_fails():
    accepted = (
        Accepted("sqs.json q", {"visible": 9, "in_flight": 0}, {"visible": 1, "in_flight": 0}, "r"),
        Accepted("sqs.json nope", ABSENT, {"visible": 1}, "r"),
    )
    actual = copy(GOLDEN)
    actual["sqs.json"]["q"]["visible"] = 1
    rows = by_check(d.classify("s/x", GOLDEN, actual, accepted))
    assert rows["sqs.json q"].result == FAILED
    assert "before value" in rows["sqs.json q"].reason
    assert rows["sqs.json nope"].result == FAILED
    assert "absent in both runs" in rows["sqs.json nope"].reason


def test_unexpected_surface_shape_is_compared_whole():
    actual = copy(GOLDEN)
    actual["sqs.json"] = ["not", "a", "mapping"]
    rows = d.classify("s/x", GOLDEN, actual)
    assert any(r.check == "sqs.json (unexpected shape)" and r.result == FAILED for r in rows)


def test_markdown_row_shows_leaf_values_and_escapes_pipes():
    actual = copy(GOLDEN)
    actual["s3.json"]["lake"]["reports/r.json"]["body"]["count"] = 2
    actual["sqs.json"]["q|x"] = actual["sqs.json"].pop("q")
    text = d.markdown(d.classify("s/x", GOLDEN, actual))
    assert "| s/x | `s3.json s3://lake/reports/r.json` | body.count=1 | body.count=2 | **failed**:" in text
    assert "`sqs.json q\\|x`" in text
    header = text.splitlines()[0]
    assert header == "| Scenario | What was compared | Before (legacy golden) | After (DAG) | Result |"


def write(tmp_path, text):
    path = tmp_path / "accepted_differences.yaml"
    path.write_text(text)
    return path


VALID = """
script: audit_archive_weekly
accepted:
- scenario: smoke
  check: sqs.json q
  before: {visible: 0}
  after: {visible: 1}
  reason: r
variants:
- name: v
  scenario: smoke
  variables: {audit_archive_delete_enabled: true}
  decision: d
  accepted:
  - check: dynamodb.json t[id=1]
    before: {id: {S: "1"}}
    after_absent: true
    reason: gone
"""


def test_load_valid(tmp_path):
    acc = d.load("audit_archive_weekly", write(tmp_path, VALID))
    assert acc.for_scenario("smoke")[0].after == {"visible": 1}
    assert acc.for_scenario("other") == ()
    variant = acc.variant("v")
    assert variant.variables == {"audit_archive_delete_enabled": True}
    assert variant.accepted[0].after is ABSENT


@pytest.mark.parametrize(
    "old, new, message",
    [
        ("  after: {visible: 1}\n  reason: r", "  after: {visible: 1}\n  reason: ''", "reason is required"),
        ("  after: {visible: 1}", "  after: {visible: 1}\n  after_absent: true", "exactly one"),
        ("  after: {visible: 1}", "  after: {visible: 0}", "nothing to accept"),
        ("  reason: r\n", "  reason: r\n  rounded: true\n", "unknown keys"),
        ("script: audit_archive_weekly", "script: analytics_daily", "script must be"),
        ("- scenario: smoke\n", "- check: x\n", "scenario is required"),
    ],
)
def test_load_rejects_unreviewable_entries(tmp_path, old, new, message):
    assert old in VALID
    with pytest.raises(ValueError, match=message):
        d.load("audit_archive_weekly", write(tmp_path, VALID.replace(old, new, 1)))
