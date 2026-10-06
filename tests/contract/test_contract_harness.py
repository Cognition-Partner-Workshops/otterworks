"""Offline regression tests for the shared contracts and the contract-test harness.

These need no running service:

    pytest tests/contract/test_contract_harness.py -v
"""

from __future__ import annotations

import json
import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import requests
import yaml
from jsonschema import Draft7Validator, ValidationError, validate

from tests.contract import test_search_contract as contract

SHARED = Path(__file__).resolve().parents[2] / "shared"
EVENT_SCHEMAS = sorted((SHARED / "events" / "schemas").glob("*.json"))
OPENAPI_SPECS = sorted((SHARED / "openapi").glob("*.yaml"))


@pytest.fixture()
def unresponsive_url() -> Iterator[str]:
    """A TCP endpoint that accepts connections but never sends a response."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(8)
    held: list[socket.socket] = []
    stop = threading.Event()

    def accept() -> None:
        server.settimeout(0.1)
        while not stop.is_set():
            try:
                conn, _ = server.accept()
                held.append(conn)
            except OSError:
                continue

    thread = threading.Thread(target=accept, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.getsockname()[1]}"
    finally:
        stop.set()
        thread.join(timeout=2)
        for conn in held:
            conn.close()
        server.close()


class TestRequestTimeout:
    def test_hung_service_fails_fast(self, unresponsive_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(contract, "HTTP_TIMEOUT_SECONDS", 0.5)
        started = time.monotonic()
        with pytest.raises(requests.exceptions.ReadTimeout):
            contract._request("GET", f"{unresponsive_url}/health")
        assert time.monotonic() - started < 5

    def test_default_timeout_is_bounded(self) -> None:
        assert 0 < contract.CONNECT_TIMEOUT_SECONDS <= 10
        assert 0 < contract.HTTP_TIMEOUT_SECONDS <= 60

    def test_live_tests_do_not_call_requests_directly(self) -> None:
        source = Path(contract.__file__).read_text()
        for call in ("requests.get(", "requests.post(", "requests.put(", "requests.delete("):
            assert call not in source, f"{call} bypasses the bounded _request timeout"


HIT = {
    "id": "f-1",
    "title": "a.pdf",
    "content_snippet": "",
    "type": "file",
    "owner_id": "u-1",
    "tags": [],
    "score": 0.0,
    "highlights": {},
}


class TestNullableResolution:
    @pytest.fixture()
    def hit_schema(self, openapi_spec: dict[str, Any]) -> dict[str, Any]:
        return contract._resolve_schema_refs(openapi_spec, openapi_spec["components"]["schemas"]["SearchHit"])

    @pytest.fixture()
    def openapi_spec(self) -> dict[str, Any]:
        with open(contract.SPEC_PATH) as f:
            return yaml.safe_load(f)

    def test_null_accepted_for_nullable_field(self, hit_schema: dict[str, Any]) -> None:
        validate(
            instance={**HIT, "created_at": None, "mime_type": None, "size": None},
            schema=hit_schema,
        )

    def test_wrong_type_still_rejected_for_nullable_field(self, hit_schema: dict[str, Any]) -> None:
        with pytest.raises(ValidationError):
            validate(instance={**HIT, "size": "big"}, schema=hit_schema)

    def test_null_rejected_for_non_nullable_field(self, hit_schema: dict[str, Any]) -> None:
        with pytest.raises(ValidationError):
            validate(instance={**HIT, "title": None}, schema=hit_schema)

    def test_nullable_enum_accepts_null(self) -> None:
        resolved = contract._resolve_schema_refs({}, {"enum": ["a", "b"], "nullable": True})
        validate(instance=None, schema=resolved)
        with pytest.raises(ValidationError):
            validate(instance="c", schema=resolved)


@pytest.mark.parametrize("path", EVENT_SCHEMAS, ids=lambda p: p.name)
class TestEventSchemas:
    def test_is_valid_draft7(self, path: Path) -> None:
        Draft7Validator.check_schema(json.loads(path.read_text()))

    def test_required_fields_are_declared(self, path: Path) -> None:
        definitions = json.loads(path.read_text()).get("definitions", {})
        assert definitions, f"{path.name} defines no events"
        for name, definition in definitions.items():
            missing = set(definition.get("required", [])) - set(definition.get("properties", {}))
            assert not missing, f"{path.name}:{name} requires undeclared fields {missing}"


def _refs(node: Any) -> Iterator[str]:
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref" and isinstance(value, str):
                yield value
            else:
                yield from _refs(value)
    elif isinstance(node, list):
        for item in node:
            yield from _refs(item)


@pytest.mark.parametrize("path", OPENAPI_SPECS, ids=lambda p: p.name)
class TestOpenApiSpecs:
    def test_is_openapi_30(self, path: Path) -> None:
        spec = yaml.safe_load(path.read_text())
        assert str(spec.get("openapi", "")).startswith("3.0")
        assert spec.get("paths")

    def test_all_refs_resolve(self, path: Path) -> None:
        spec = yaml.safe_load(path.read_text())
        for ref in set(_refs(spec)):
            assert ref.startswith("#/"), f"external $ref not supported: {ref}"
            contract._resolve_ref(spec, ref)
