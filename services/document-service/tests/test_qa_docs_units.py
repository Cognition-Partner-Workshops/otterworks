"""QA (docs area): pure-logic unit tests for document-service helpers."""

import hashlib
import uuid
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.document import DocumentCreate, DocumentPatch, DocumentUpdate
from app.services.document_query_repository import DocumentQueryRepository
from app.services.document_service import DocumentService, _word_count
from app.services.export_archive import ExportArchive
from app.services.render_cache import RenderCache
from app.services.share_link import TOKEN_LENGTH, ShareLinkService


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", 0),
        ("one", 1),
        ("one two  three", 3),
        ("  leading and trailing  ", 3),
        ("line\nbreak\ttab", 3),
    ],
)
def test_word_count(text, expected):
    assert _word_count(text) == expected


@pytest.mark.parametrize(
    ("total", "size", "expected"),
    [(0, 20, 1), (1, 20, 1), (20, 20, 1), (21, 20, 2), (100, 7, 15), (5, 0, 1)],
)
def test_paginate(total, size, expected):
    assert DocumentService.paginate(total, 1, size) == expected


def test_document_create_defaults():
    data = DocumentCreate(title="t")
    assert data.content == ""
    assert data.content_type == "text/markdown"
    assert data.owner_id is None


def test_document_update_requires_title():
    with pytest.raises(ValidationError):
        DocumentUpdate(content="x")


@pytest.mark.parametrize("field", ["title", "content", "content_type"])
def test_document_patch_rejects_null(field):
    with pytest.raises(ValidationError):
        DocumentPatch(**{field: None})


def test_document_patch_tracks_only_set_fields():
    patch = DocumentPatch(title="Renamed")
    assert patch.model_fields_set == {"title"}


def _doc(**overrides):
    base = {"id": uuid.uuid4(), "title": "Title", "content": "Body", "version": 1}
    base.update(overrides)
    return SimpleNamespace(**base)


def test_export_formats_content_types():
    svc = DocumentService(db=None)  # type: ignore[arg-type]
    doc = _doc()
    assert svc.export_document(doc, "html")[1] == "text/html"
    assert svc.export_document(doc, "markdown") == ("# Title\n\nBody", "text/markdown")
    assert svc.export_document(doc, "pdf")[1] == "application/pdf"


def test_export_html_escapes_title_and_body():
    svc = DocumentService(db=None)  # type: ignore[arg-type]
    body, _ = svc.export_document(_doc(title="<b>x</b>", content="a & b"), "html")
    assert "<b>x</b>" not in body
    assert "&lt;b&gt;x&lt;/b&gt;" in body
    assert "a &amp; b" in body


def test_share_token_length_and_determinism():
    svc = ShareLinkService(salt="s")
    token = svc.mint_token("doc")
    assert len(token) == TOKEN_LENGTH
    assert svc.mint_token("doc") == token


def test_share_token_depends_on_salt():
    assert ShareLinkService(salt="a").mint_token("doc") != ShareLinkService(salt="b").mint_token(
        "doc"
    )


def test_share_token_is_not_plain_md5_of_public_inputs():
    """A share token must not be forgeable from the document id and a default salt."""
    doc_id = str(uuid.uuid4())
    forged = hashlib.md5(f"{doc_id}:otterworks-share".encode()).hexdigest()[:TOKEN_LENGTH]  # noqa: S324
    assert ShareLinkService(salt="otterworks-share").mint_token(doc_id) != forged


def test_export_archive_refuses_path_traversal(tmp_path):
    base = tmp_path / "exports"
    base.mkdir()
    (tmp_path / "secret.txt").write_text("top secret", encoding="utf-8")
    archive = ExportArchive(base_dir=str(base))
    with pytest.raises((OSError, ValueError, PermissionError)):
        archive.read_export("../secret.txt")


def test_export_archive_refuses_absolute_path(tmp_path):
    (tmp_path / "secret.txt").write_text("top secret", encoding="utf-8")
    archive = ExportArchive(base_dir=str(tmp_path / "exports"))
    with pytest.raises((OSError, ValueError, PermissionError)):
        archive.read_export(str(tmp_path / "secret.txt"))


def test_render_cache_keys_by_version_and_format():
    cache = RenderCache()
    doc = _doc()
    cache.put(doc, "html", "<h1>v1</h1>", "text/html")
    assert cache.get(doc, "html") == ("<h1>v1</h1>", "text/html")
    assert cache.get(doc, "markdown") is None
    doc.version = 2
    assert cache.get(doc, "html") is None
    cache.clear()
    assert len(cache) == 0


def test_render_cache_is_bounded():
    cache = RenderCache()
    for i in range(5000):
        cache.put(_doc(version=i), "html", "x", "text/html")
    assert len(cache) < 5000, "render cache grows without bound"


def test_query_repository_where_basic_clauses():
    repo = DocumentQueryRepository(db=None)  # type: ignore[arg-type]
    where = repo._where(None, None, None)
    assert "is_deleted = false" in where
    assert "is_template = false" in where


def test_query_repository_where_does_not_inline_user_input():
    repo = DocumentQueryRepository(db=None)  # type: ignore[arg-type]
    where = repo._where(None, "x' OR '1'='1", None)
    assert "OR '1'='1" not in where, "title filter is interpolated into SQL"
