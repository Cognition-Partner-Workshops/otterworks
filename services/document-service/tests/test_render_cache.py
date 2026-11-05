"""The render cache stays bounded no matter how many document versions are exported."""

import uuid

from app.models.document import Document
from app.services.render_cache import RenderCache


def test_render_cache_stays_bounded_past_capacity():
    cache = RenderCache()
    doc_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    docs = [
        Document(id=doc_id, title="Doc", content=f"v{v}", owner_id=owner_id, version=v)
        for v in range(1, 5001)
    ]
    for doc in docs[:-1]:
        cache.put(doc, "markdown", doc.content, "text/markdown")

    hot_doc = docs[-len(cache) - 1]
    lru_doc = docs[-len(cache)]
    assert cache.get(hot_doc, "markdown") == (hot_doc.content, "text/markdown")
    cache.put(docs[-1], "markdown", docs[-1].content, "text/markdown")

    assert len(cache) <= 1000
    assert cache.get(hot_doc, "markdown") == (hot_doc.content, "text/markdown")
    assert cache.get(lru_doc, "markdown") is None
    assert cache.get(docs[0], "markdown") is None
    assert cache.get(docs[-1], "markdown") == ("v5000", "text/markdown")
