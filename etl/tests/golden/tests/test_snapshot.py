import gzip
import json

from harness.snapshot import decode_body, dumps


def test_gzip_json_is_decompressed_and_parsed():
    out = decode_body(gzip.compress(json.dumps({"a": 1}).encode(), mtime=0))
    assert out == {"gzip": True, "format": "json", "body": {"a": 1}}


def test_jsonl_keeps_line_order_and_trailing_newline():
    out = decode_body(b'{"b": 2}\n{"a": 1}\n')
    assert out == {
        "gzip": False,
        "format": "jsonl",
        "body": [{"b": 2}, {"a": 1}],
        "trailing_newline": True,
    }
    assert decode_body(b'{"b": 2}\n{"a": 1}')["trailing_newline"] is False


def test_text_and_binary():
    assert decode_body(b"hello\nworld")["format"] == "text"
    assert decode_body(b"\xff\xfe\x00")["format"] == "base64"
    assert decode_body(b"")["format"] == "text"


def test_dumps_is_canonical():
    assert (
        dumps({"b": 1, "a": [2, 1]})
        == '{\n  "a": [\n    2,\n    1\n  ],\n  "b": 1\n}\n'
    )
