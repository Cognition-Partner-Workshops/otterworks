"""Render-cache retention must stay bounded across edit-then-export traffic."""

from app.models.document import Document
from app.services.render_cache import RenderCache


def test_render_cache_caps_entries_across_document_versions() -> None:
    cache = RenderCache()
    document = Document(id="edited-document", title="Draft", content="Draft content")

    for version in range(1, 5001):
        document.version = version
        cache.put(document, "html", f"<p>Version {version}</p>", "text/html")

    # incident/scenarios.yaml cache-leak correct_fix requires bounded retention;
    # 1024 entries is the expected maximum for this edit-then-export workload.
    assert len(cache) <= 1024
