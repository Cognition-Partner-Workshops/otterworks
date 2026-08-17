import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "tp_dbx"))

import custbill_layout as layout
import parse_sql


def make_record(
    cust_id="CUST000001",
    cust_name="Alice Example",
    bill_date="20230131",
    amount="000000540688",
    currency="USD",
    record_type="01",
):
    fields = (
        cust_id.ljust(10),
        cust_name.ljust(30),
        bill_date,
        amount,
        currency,
        record_type,
    )
    result = "".join(fields).encode("ascii")
    assert len(result) == 65
    return result


def make_file(*body, trailer_count=None):
    if trailer_count is None:
        trailer_count = len(body)
    lines = [b"HDR CBCUST01", *body, b"TRL" + f"{trailer_count:010d}".encode("ascii")]
    return b"\n".join(lines) + b"\n"


def test_clean_two_record_file_preserves_integer_cents_and_iso_dates():
    first = make_record(
        cust_id="CUST000001",
        cust_name="Alice Example",
        bill_date="20230131",
        amount="000000540688",
    )
    second = make_record(
        cust_id="CUST000002",
        cust_name="Bob Example",
        bill_date="20240229",
        amount="000000000001",
        record_type="02",
    )

    result = layout.parse_file("clean.dat", make_file(first, second))

    assert not result.failed
    assert len(result.records) == 2
    assert not result.rejects
    assert [(record.amount_cents, record.bill_date) for record in result.records] == [
        (540688, "2023-01-31"),
        (1, "2024-02-29"),
    ]


def test_non_numeric_amount_is_quarantined_with_original_bytes():
    bad = make_record(amount="00000054X688")

    result = layout.parse_file("bad-amount.dat", make_file(bad))

    assert len(result.records) == 0
    assert len(result.rejects) == 1
    reject = result.rejects[0]
    assert reject.reason_code == "non_numeric_amount"
    assert base64.b64decode(reject.raw_bytes_base64) == bad


def test_invalid_calendar_date_is_rejected_but_leap_day_is_accepted():
    invalid = make_record(cust_id="CUST000001", bill_date="20230231")
    leap_day = make_record(cust_id="CUST000002", bill_date="20240229")

    result = layout.parse_file("dates.dat", make_file(invalid, leap_day))

    assert len(result.records) == 1
    assert result.records[0].cust_id == "CUST000002"
    assert result.records[0].bill_date == "2024-02-29"
    assert [reject.reason_code for reject in result.rejects] == ["invalid_calendar_date"]


def test_short_and_long_lines_are_quarantined_as_bad_record_length():
    valid = make_record()
    short = valid[:-1]
    long = valid + b"X"

    result = layout.parse_file("lengths.dat", make_file(short, long))

    assert len(result.records) == 0
    assert [reject.reason_code for reject in result.rejects] == [
        "bad_record_length",
        "bad_record_length",
    ]


def test_invalid_utf8_byte_is_quarantined_without_raising():
    bad_encoding = make_record()
    bad_encoding = bad_encoding[:15] + b"\xff" + bad_encoding[16:]

    result = layout.parse_file("encoding.dat", make_file(bad_encoding))

    assert len(result.records) == 0
    assert len(result.rejects) == 1
    assert result.rejects[0].reason_code == "encoding_invalid_byte"
    assert base64.b64decode(result.rejects[0].raw_bytes_base64) == bad_encoding


def test_trailer_mismatch_fails_file_and_quarantines_every_body_line():
    first = make_record(cust_id="CUST000001")
    second = make_record(cust_id="CUST000002")

    result = layout.parse_file("mismatch.dat", make_file(first, second, trailer_count=1))

    assert result.failed
    assert result.records == []
    reasons = [reject.reason_code for reject in result.rejects]
    assert reasons.count("trailer_count_mismatch") == 1
    assert reasons.count("file_failed_trailer_mismatch") == 2
    mismatch = next(reject for reject in result.rejects if reject.reason_code == "trailer_count_mismatch")
    assert "trailer=1" in mismatch.detail
    assert "records=2" in mismatch.detail
    quarantined_lines = {
        reject.source_line
        for reject in result.rejects
        if reject.reason_code == "file_failed_trailer_mismatch"
    }
    assert quarantined_lines == {2, 3}


def test_missing_trailer_fails_file():
    body = make_record()

    result = layout.parse_file("missing-trailer.dat", b"HDR CBCUST01\n" + body + b"\n")

    assert result.failed
    assert result.records == []
    assert "missing_trailer" in {reject.reason_code for reject in result.rejects}


def test_blank_customer_id_and_name_are_rejected():
    blank_id = make_record(cust_id="", cust_name="Named Customer")
    blank_name = make_record(cust_id="CUST000002", cust_name="")

    result = layout.parse_file("missing-fields.dat", make_file(blank_id, blank_name))

    assert result.records == []
    assert sorted(reject.reason_code for reject in result.rejects) == [
        "missing_cust_id",
        "missing_cust_name",
    ]


def test_escapes_single_quotes_and_backslashes():
    assert parse_sql.esc(r"O'Reilly\billing") == r"O''Reilly\\billing"
