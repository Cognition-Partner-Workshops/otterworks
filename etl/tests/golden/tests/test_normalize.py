from harness.normalize import normalize, placeholder


def s3_files(body, fmt="json"):
    return {"s3.json": {"bucket": {"key": {"format": fmt, "body": body}}}}


def test_replaces_generated_at_anywhere_in_json_bodies():
    files = s3_files(
        {
            "generated_at": "2026-03-15T02:00:00+00:00",
            "nested": [{"generated_at": "2026-03-15T02:00:00Z"}],
        }
    )
    out, replaced = normalize(files)
    body = out["s3.json"]["bucket"]["key"]["body"]
    assert replaced == 2
    assert body["generated_at"] == placeholder("generated_at")
    assert body["nested"][0]["generated_at"] == placeholder("generated_at")


def test_jsonl_bodies_and_durations():
    out, replaced = normalize(
        s3_files([{"duration_seconds": 1.5}, {"duration_ms": 7}], fmt="jsonl")
    )
    assert replaced == 2
    assert out["s3.json"]["bucket"]["key"]["body"] == [
        {"duration_seconds": placeholder("duration_seconds")},
        {"duration_ms": placeholder("duration_ms")},
    ]


def test_leaves_everything_else_verbatim():
    body = {
        "timestamp": "2026-03-15T02:00:00Z",
        "report_date": "2026-03-15",
        "created_at": "2026-03-15T00:00:00Z",
        "total": 3,
    }
    out, replaced = normalize(s3_files(body))
    assert replaced == 0
    assert out["s3.json"]["bucket"]["key"]["body"] == body


def test_malformed_volatile_values_are_not_hidden():
    body = {"generated_at": "yesterday", "duration_seconds": "fast"}
    out, replaced = normalize(s3_files(body))
    assert replaced == 0
    assert out["s3.json"]["bucket"]["key"]["body"] == body


def test_text_bodies_are_untouched():
    out, replaced = normalize(
        s3_files('{"generated_at": "2026-03-15T02:00:00Z"}', fmt="text")
    )
    assert replaced == 0


def test_postgres_only_listed_columns():
    files = {
        "postgres.json": {
            "analytics_daily_summary": {
                "rows": [
                    {
                        "report_date": "2026-03-15",
                        "updated_at": "2026-10-07T13:00:00.1+00:00",
                    }
                ]
            },
            "other": {"rows": [{"updated_at": "2026-10-07T13:00:00+00:00"}]},
        }
    }
    out, replaced = normalize(files)
    assert replaced == 1
    assert out["postgres.json"]["analytics_daily_summary"]["rows"][0] == {
        "report_date": "2026-03-15",
        "updated_at": placeholder("updated_at"),
    }
    assert (
        out["postgres.json"]["other"]["rows"][0]["updated_at"]
        == "2026-10-07T13:00:00+00:00"
    )


def test_does_not_mutate_input_and_is_idempotent():
    files = s3_files({"generated_at": "2026-03-15T02:00:00Z"})
    out, _ = normalize(files)
    assert (
        files["s3.json"]["bucket"]["key"]["body"]["generated_at"]
        == "2026-03-15T02:00:00Z"
    )
    again, replaced = normalize(out)
    assert again == out and replaced == 0
