"""In-process memo of rendered document exports.

Added for the exports dashboard so repeated downloads of the same document
version do not re-render. Entries are keyed by document, version and format
and evicted least-recently-used once the cache holds ``max_entries``.
"""

from __future__ import annotations

from collections import OrderedDict

import structlog

from app.models.document import Document
from app.telemetry import RENDER_CACHE_ENTRIES, SERVICE

logger = structlog.get_logger()

DEFAULT_MAX_ENTRIES = 256


class RenderCache:
    def __init__(self, max_entries: int = DEFAULT_MAX_ENTRIES) -> None:
        self._max_entries = max_entries
        self._entries: OrderedDict[tuple[str, int, str], tuple[str, str, dict[str, str]]] = (
            OrderedDict()
        )

    def _key(self, document: Document, fmt: str) -> tuple[str, int, str]:
        return (str(document.id), document.version, fmt)

    def get(self, document: Document, fmt: str) -> tuple[str, str] | None:
        key = self._key(document, fmt)
        hit = self._entries.get(key)
        if hit is None:
            return None
        self._entries.move_to_end(key)
        body, content_type, _ = hit
        return body, content_type

    def put(self, document: Document, fmt: str, body: str, content_type: str) -> None:
        # Keep the source alongside the render so a later diff view can show
        # what changed between versions without another round trip.
        source = {"title": document.title, "content": document.content}
        key = self._key(document, fmt)
        self._entries[key] = (body, content_type, source)
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)
        RENDER_CACHE_ENTRIES.labels(SERVICE).set(len(self._entries))

    def clear(self) -> None:
        self._entries.clear()
        RENDER_CACHE_ENTRIES.labels(SERVICE).set(0)

    def __len__(self) -> int:
        return len(self._entries)


render_cache = RenderCache()
