"""In-process rendered-export memo."""

import uuid
from types import SimpleNamespace

import pytest
from prometheus_client import REGISTRY

from app.services.render_cache import RenderCache
from app.telemetry import SERVICE


def _doc(version: int = 1, doc_id: uuid.UUID | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=doc_id or uuid.uuid4(), version=version, title="Title", content="Body"
    )


def _gauge() -> float | None:
    return REGISTRY.get_sample_value("otterworks_render_cache_entries", {"service": SERVICE})


@pytest.fixture
def cache() -> RenderCache:
    return RenderCache()


def test_miss_returns_none(cache: RenderCache) -> None:
    assert cache.get(_doc(), "html") is None
    assert len(cache) == 0


def test_put_then_get_returns_body_and_content_type(cache: RenderCache) -> None:
    doc = _doc()
    cache.put(doc, "html", "<h1>Title</h1>", "text/html")
    assert cache.get(doc, "html") == ("<h1>Title</h1>", "text/html")
    assert len(cache) == 1
    assert _gauge() == 1


def test_entries_are_keyed_by_document_version_and_format(cache: RenderCache) -> None:
    doc = _doc(version=1)
    cache.put(doc, "html", "v1 html", "text/html")

    assert cache.get(doc, "markdown") is None
    assert cache.get(_doc(version=2, doc_id=doc.id), "html") is None
    assert cache.get(_doc(version=1), "html") is None

    cache.put(doc, "markdown", "v1 md", "text/markdown")
    assert cache.get(doc, "markdown") == ("v1 md", "text/markdown")
    assert len(cache) == 2


def test_put_same_key_overwrites(cache: RenderCache) -> None:
    doc = _doc()
    cache.put(doc, "html", "old", "text/html")
    cache.put(doc, "html", "new", "text/html")
    assert cache.get(doc, "html") == ("new", "text/html")
    assert len(cache) == 1


def test_clear_empties_cache_and_gauge(cache: RenderCache) -> None:
    cache.put(_doc(), "html", "x", "text/html")
    cache.clear()
    assert len(cache) == 0
    assert _gauge() == 0
