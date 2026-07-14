"""Backend-agnostic in-memory search analytics.

The analytics store is shared across every search backend (MeiliSearch,
OpenSearch, ...) so switching the backend never changes the behaviour of
``GET /api/v1/search/analytics``.
"""

from __future__ import annotations

import threading
import time
from typing import Any

from app.models.search_result import AnalyticsData

# In-memory analytics store
_analytics_lock = threading.Lock()
_search_analytics: dict[str, Any] = {
    "queries": [],
    "total_searches": 0,
    "total_results": 0,
}

MAX_ANALYTICS_ENTRIES = 10000


def record_search_analytics(query: str, result_count: int) -> None:
    """Record a search query for analytics purposes."""
    with _analytics_lock:
        _search_analytics["queries"].append(
            {"query": query, "result_count": result_count, "timestamp": time.time()}
        )
        _search_analytics["total_searches"] += 1
        _search_analytics["total_results"] += result_count
        if len(_search_analytics["queries"]) > MAX_ANALYTICS_ENTRIES:
            _search_analytics["queries"] = _search_analytics["queries"][-MAX_ANALYTICS_ENTRIES:]


def get_search_analytics() -> AnalyticsData:
    """Compute search analytics from recorded queries."""
    with _analytics_lock:
        queries = list(_search_analytics["queries"])
        total_searches = _search_analytics["total_searches"]
        total_results = _search_analytics["total_results"]

    query_counts: dict[str, int] = {}
    zero_result_counts: dict[str, int] = {}
    for entry in queries:
        q = entry["query"]
        query_counts[q] = query_counts.get(q, 0) + 1
        if entry["result_count"] == 0:
            zero_result_counts[q] = zero_result_counts.get(q, 0) + 1

    popular = sorted(query_counts.items(), key=lambda x: x[1], reverse=True)[:20]
    zero_results = sorted(zero_result_counts.items(), key=lambda x: x[1], reverse=True)[:20]

    avg_results = total_results / total_searches if total_searches > 0 else 0.0

    return AnalyticsData(
        popular_queries=[{"query": q, "count": c} for q, c in popular],
        zero_result_queries=[{"query": q, "count": c} for q, c in zero_results],
        total_searches=total_searches,
        avg_results_per_query=round(avg_results, 2),
    )
