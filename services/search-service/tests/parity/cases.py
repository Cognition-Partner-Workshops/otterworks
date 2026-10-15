"""Ordered parity cases for the search service.

Each entry is either an HTTP request (``method``/``path``) or a control step
(``action``) that changes the environment around the service. Order matters:
later cases depend on the index state and counters left by earlier ones.
"""

from __future__ import annotations

from typing import Any

TOKEN = "parity-service-token"
CHAOS_KEY = "chaos:search-service:suggest_500"

U1 = {"X-User-ID": "parity-user-1"}
U2 = {"X-User-ID": "parity-user-2"}
BEARER = {"Authorization": f"Bearer {TOKEN}"}
JSON = {"Content-Type": "application/json"}

ALLOWED_ORIGIN = "http://localhost:3000"
ALLOWED_ORIGIN_2 = "http://localhost:4200"
DISALLOWED_ORIGIN = "http://evil.example"

S = "/api/v1/search"

DOC_1 = {
    "id": "parity-doc-1",
    "title": "Otter Quarterly Report",
    "content": "Quarterly revenue for the otter colony grew steadily across every river.",
    "owner_id": "parity-user-1",
    "tags": ["finance", "report"],
    "created_at": "2026-01-15T10:00:00Z",
    "updated_at": "2026-01-16T10:00:00Z",
}
DOC_2 = {
    "id": "parity-doc-2",
    "title": "Otter Habitat Notes",
    "content": "Field notes on otter dens, river banks and kelp forests.",
    "owner_id": "parity-user-2",
    "tags": ["research"],
    "created_at": "2026-02-01T09:30:00Z",
    "updated_at": "2026-02-02T09:30:00Z",
}
FILE_1 = {
    "id": "parity-file-1",
    "name": "otter-photo.png",
    "mime_type": "image/png",
    "owner_id": "parity-user-1",
    "folder_id": "parity-folder-1",
    "tags": ["media"],
    "size": 2048,
    "created_at": "2026-01-20T12:00:00Z",
    "updated_at": "2026-01-20T12:00:00Z",
}
FILE_2 = {
    "id": "parity-file-2",
    "name": "otter-budget.xlsx",
    "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "owner_id": "parity-user-2",
    "folder_id": "parity-folder-2",
    "tags": ["finance"],
    "size": 4096,
    "created_at": "2026-02-10T08:00:00Z",
}


def _req(
    name: str,
    method: str,
    path: str,
    headers: dict[str, str] | None = None,
    json: Any = None,
    raw: str | None = None,
) -> dict[str, Any]:
    case: dict[str, Any] = {
        "name": name,
        "method": method,
        "path": path,
        "headers": dict(headers or {}),
    }
    if json is not None:
        case["headers"].setdefault("Content-Type", "application/json")
        case["json"] = json
    elif raw is not None:
        case["raw"] = raw
    return case


def _act(name: str, action: str, **kwargs: Any) -> dict[str, Any]:
    return {"name": name, "action": action, **kwargs}


CASES: list[dict[str, Any]] = [
    # --- environment reset -------------------------------------------------
    _act("reset.chaos_flag_cleared", "redis_del", key=CHAOS_KEY),
    _act("reset.service_restarted", "restart_service"),
    # --- health / metrics --------------------------------------------------
    _req("health.alive", "GET", "/health"),
    _req("health.ready_ok", "GET", "/health/ready"),
    _req("metrics.initial", "GET", "/metrics"),
    _req("health.head", "HEAD", "/health"),
    # --- reindex wipes indices to a known empty state ----------------------
    _req("reindex.bearer", "POST", f"{S}/reindex", BEARER),
    _req("reindex.user", "POST", f"{S}/reindex", U1),
    # --- indexing ----------------------------------------------------------
    _req("index.document.doc1", "POST", f"{S}/index/document", U1, json=DOC_1),
    _req("index.document.doc2", "POST", f"{S}/index/document", BEARER, json=DOC_2),
    _req("index.file.file1", "POST", f"{S}/index/file", U1, json=FILE_1),
    _req("index.file.file2", "POST", f"{S}/index/file", BEARER, json=FILE_2),
    _req(
        "index.document.reindex_same_id", "POST", f"{S}/index/document", U1, json=DOC_1
    ),
    _req(
        "index.document.missing_id",
        "POST",
        f"{S}/index/document",
        U1,
        json={"title": "No id"},
    ),
    _req(
        "index.document.missing_title",
        "POST",
        f"{S}/index/document",
        U1,
        json={"id": "x"},
    ),
    _req("index.document.empty_object", "POST", f"{S}/index/document", U1, json={}),
    _req("index.document.json_array", "POST", f"{S}/index/document", U1, json=[1]),
    _req("index.document.no_body", "POST", f"{S}/index/document", U1),
    _req(
        "index.document.no_content_type",
        "POST",
        f"{S}/index/document",
        U1,
        raw='{"id": "a", "title": "b"}',
    ),
    _req(
        "index.document.invalid_json",
        "POST",
        f"{S}/index/document",
        {**U1, **JSON},
        raw="{not json",
    ),
    _req(
        "index.file.missing_id", "POST", f"{S}/index/file", U1, json={"name": "a.txt"}
    ),
    _req("index.file.missing_name", "POST", f"{S}/index/file", U1, json={"id": "x"}),
    _req("index.file.empty_object", "POST", f"{S}/index/file", U1, json={}),
    _req("index.file.no_body", "POST", f"{S}/index/file", U1),
    _req(
        "index.file.invalid_json",
        "POST",
        f"{S}/index/file",
        {**U1, **JSON},
        raw="{not json",
    ),
    # --- search ------------------------------------------------------------
    _req("search.no_slash.user1", "GET", f"{S}?q=otter", U1),
    _req("search.slash.user1", "GET", f"{S}/?q=otter", U1),
    _req("search.no_slash.user2", "GET", f"{S}?q=otter", U2),
    _req("search.bearer_all_owners", "GET", f"{S}/?q=otter", BEARER),
    _req("search.type_document", "GET", f"{S}/?q=otter&type=document", BEARER),
    _req("search.type_file", "GET", f"{S}/?q=otter&type=file", BEARER),
    _req("search.type_unknown", "GET", f"{S}/?q=otter&type=folder", BEARER),
    _req("search.highlight_content", "GET", f"{S}/?q=revenue", U1),
    _req("search.page2_size1", "GET", f"{S}/?q=otter&page=2&size=1", BEARER),
    _req("search.page_beyond", "GET", f"{S}/?q=otter&page=50&size=10", BEARER),
    _req("search.page_zero_clamped", "GET", f"{S}/?q=otter&page=0&size=0", BEARER),
    _req("search.size_over_max_clamped", "GET", f"{S}/?q=otter&size=1000", BEARER),
    _req("search.negative_page", "GET", f"{S}/?q=otter&page=-3", BEARER),
    _req("search.invalid_page", "GET", f"{S}/?q=otter&page=abc", U1),
    _req("search.invalid_size", "GET", f"{S}/?q=otter&size=xyz", U1),
    _req("search.float_page", "GET", f"{S}/?q=otter&page=1.5", U1),
    _req("search.invalid_page_missing_q", "GET", f"{S}/?page=abc", U1),
    _req("search.missing_q", "GET", f"{S}/", U1),
    _req("search.empty_q", "GET", f"{S}?q=", U1),
    _req("search.no_results", "GET", f"{S}/?q=zebra", U1),
    _req("search.quote_in_type", "GET", f"{S}/?q=otter&type=a%22b", BEARER),
    _req("search.quote_in_user_id", "GET", f"{S}/?q=otter", {"X-User-ID": 'u"1'}),
    _req("search.unicode_q", "GET", f"{S}/?q=%C3%B6tter", U1),
    # --- suggest -----------------------------------------------------------
    _req("suggest.missing_q", "GET", f"{S}/suggest", U1),
    _req("suggest.short_prefix", "GET", f"{S}/suggest?q=o", U1),
    _req("suggest.normal", "GET", f"{S}/suggest?q=ott", U1),
    _req("suggest.no_match", "GET", f"{S}/suggest?q=zzzz", U1),
    _req("suggest.trailing_slash", "GET", f"{S}/suggest/?q=ott", U1),
    # --- advanced ----------------------------------------------------------
    _req("advanced.query", "POST", f"{S}/advanced", U1, json={"q": "otter"}),
    _req("advanced.bearer_all", "POST", f"{S}/advanced", BEARER, json={"q": "otter"}),
    _req(
        "advanced.type_file",
        "POST",
        f"{S}/advanced",
        BEARER,
        json={"q": "otter", "type": "file"},
    ),
    _req(
        "advanced.tags",
        "POST",
        f"{S}/advanced",
        BEARER,
        json={"q": "otter", "tags": ["finance"]},
    ),
    _req(
        "advanced.dates",
        "POST",
        f"{S}/advanced",
        BEARER,
        json={
            "q": "otter",
            "date_from": "2026-01-01T00:00:00Z",
            "date_to": "2026-01-31T23:59:59Z",
        },
    ),
    _req(
        "advanced.paging",
        "POST",
        f"{S}/advanced",
        BEARER,
        json={"q": "otter", "page": 2, "size": 1},
    ),
    _req(
        "advanced.paging_strings",
        "POST",
        f"{S}/advanced",
        BEARER,
        json={"q": "otter", "page": "1", "size": "2"},
    ),
    _req("advanced.empty_object", "POST", f"{S}/advanced", U1, json={}),
    _req(
        "advanced.invalid_page",
        "POST",
        f"{S}/advanced",
        U1,
        json={"q": "otter", "page": "x"},
    ),
    _req(
        "advanced.invalid_size",
        "POST",
        f"{S}/advanced",
        U1,
        json={"q": "otter", "size": None},
    ),
    _req("advanced.no_body", "POST", f"{S}/advanced", U1),
    _req(
        "advanced.invalid_json",
        "POST",
        f"{S}/advanced",
        {**U1, **JSON},
        raw="{not json",
    ),
    _req("advanced.json_null", "POST", f"{S}/advanced", {**U1, **JSON}, raw="null"),
    # --- analytics ---------------------------------------------------------
    _req("analytics.after_searches", "GET", f"{S}/analytics", U1),
    # --- delete ------------------------------------------------------------
    _req("delete.document", "DELETE", f"{S}/index/document/parity-doc-2", BEARER),
    _req(
        "delete.document_again_not_found",
        "DELETE",
        f"{S}/index/document/parity-doc-2",
        BEARER,
    ),
    _req("delete.file", "DELETE", f"{S}/index/file/parity-file-2", U1),
    _req("delete.invalid_type", "DELETE", f"{S}/index/folder/x", U1),
    _req("delete.missing_id", "DELETE", f"{S}/index/document/", U1),
    _req("search.after_delete", "GET", f"{S}/?q=otter", BEARER),
    # --- routing errors ----------------------------------------------------
    _req("routing.unknown_api_path", "GET", "/api/v1/nope", U1),
    _req("routing.unknown_root_path", "GET", "/nope", U1),
    _req("routing.unknown_search_subpath", "GET", f"{S}/nope", U1),
    _req("routing.wrong_method.post_search", "POST", f"{S}/", U1, json={}),
    _req("routing.wrong_method.get_advanced", "GET", f"{S}/advanced", U1),
    _req("routing.wrong_method.get_reindex", "GET", f"{S}/reindex", U1),
    _req("routing.wrong_method.get_index_document", "GET", f"{S}/index/document", U1),
    _req("routing.wrong_method.put_health", "PUT", "/health"),
    _req("routing.wrong_method.post_metrics", "POST", "/metrics"),
    # --- auth (REQUIRE_AUTH=true) -----------------------------------------
    _req("auth.none.search", "GET", f"{S}?q=otter"),
    _req("auth.none.search_slash", "GET", f"{S}/?q=otter"),
    _req("auth.none.suggest", "GET", f"{S}/suggest?q=ott"),
    _req("auth.none.advanced", "POST", f"{S}/advanced", json={"q": "otter"}),
    _req("auth.none.analytics", "GET", f"{S}/analytics"),
    _req("auth.none.index_document", "POST", f"{S}/index/document", json=DOC_1),
    _req("auth.none.delete", "DELETE", f"{S}/index/document/parity-doc-1"),
    _req("auth.none.reindex", "POST", f"{S}/reindex"),
    _req("auth.none.unknown_path", "GET", "/api/v1/nope"),
    _req("auth.none.unknown_root_path", "GET", "/nope"),
    _req("auth.none.wrong_method", "GET", f"{S}/advanced"),
    _req("auth.none.health", "GET", "/health"),
    _req("auth.none.health_ready", "GET", "/health/ready"),
    _req("auth.none.metrics", "GET", "/metrics"),
    _req("auth.none.health_prefix_path", "GET", "/healthcheck"),
    _req("auth.none.metrics_prefix_path", "GET", "/metrics/extra"),
    _req("auth.blank_user_id", "GET", f"{S}?q=otter", {"X-User-ID": "   "}),
    _req("auth.user_id", "GET", f"{S}?q=otter", U1),
    _req("auth.bearer_valid", "GET", f"{S}?q=otter", BEARER),
    _req(
        "auth.bearer_lowercase_scheme",
        "GET",
        f"{S}?q=otter",
        {"Authorization": f"bearer {TOKEN}"},
    ),
    _req(
        "auth.bearer_invalid",
        "GET",
        f"{S}?q=otter",
        {"Authorization": "Bearer wrong-token"},
    ),
    _req(
        "auth.basic_scheme", "GET", f"{S}?q=otter", {"Authorization": f"Basic {TOKEN}"}
    ),
    _req(
        "auth.bearer_invalid_with_user_id",
        "GET",
        f"{S}?q=otter",
        {"Authorization": "Bearer wrong-token", **U2},
    ),
    _req("auth.bearer_valid.reindex_not_run", "GET", f"{S}/reindex", BEARER),
    # --- CORS --------------------------------------------------------------
    _req(
        "cors.preflight.allowed.no_creds",
        "OPTIONS",
        f"{S}/",
        {
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "x-user-id",
        },
    ),
    _req(
        "cors.preflight.allowed.with_user_id",
        "OPTIONS",
        f"{S}/",
        {
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "x-user-id",
            **U1,
        },
    ),
    _req(
        "cors.preflight.allowed_4200.advanced",
        "OPTIONS",
        f"{S}/advanced",
        {
            "Origin": ALLOWED_ORIGIN_2,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-user-id",
            **U1,
        },
    ),
    _req(
        "cors.preflight.disallowed.no_creds",
        "OPTIONS",
        f"{S}/",
        {
            "Origin": DISALLOWED_ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "x-user-id",
        },
    ),
    _req(
        "cors.preflight.disallowed.with_user_id",
        "OPTIONS",
        f"{S}/",
        {
            "Origin": DISALLOWED_ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "x-user-id",
            **U1,
        },
    ),
    _req(
        "cors.preflight.health",
        "OPTIONS",
        "/health",
        {"Origin": ALLOWED_ORIGIN, "Access-Control-Request-Method": "GET"},
    ),
    _req(
        "cors.simple.allowed", "GET", f"{S}/?q=otter", {"Origin": ALLOWED_ORIGIN, **U1}
    ),
    _req(
        "cors.simple.disallowed",
        "GET",
        f"{S}/?q=otter",
        {"Origin": DISALLOWED_ORIGIN, **U1},
    ),
    _req(
        "cors.simple.allowed.unauthorized",
        "GET",
        f"{S}/?q=otter",
        {"Origin": ALLOWED_ORIGIN},
    ),
    _req("cors.simple.allowed.health", "GET", "/health", {"Origin": ALLOWED_ORIGIN}),
    # --- planted chaos flag (must survive the translation) -----------------
    _act("chaos.suggest_500.set", "redis_set", key=CHAOS_KEY, value="1"),
    _req("chaos.suggest.normal_500", "GET", f"{S}/suggest?q=ott", U1),
    _req("chaos.suggest.no_match_500", "GET", f"{S}/suggest?q=zzzz", U1),
    _req("chaos.suggest.short_prefix_ok", "GET", f"{S}/suggest?q=o", U1),
    _req("chaos.search_unaffected", "GET", f"{S}/?q=otter", U1),
    _act("chaos.suggest_500.cleared", "redis_del", key=CHAOS_KEY),
    _req("chaos.suggest.recovered", "GET", f"{S}/suggest?q=ott", U1),
    # --- MeiliSearch down --------------------------------------------------
    _act("meili.stopped", "stop_meilisearch"),
    _req("meili_down.health", "GET", "/health"),
    _req("meili_down.health_ready_503", "GET", "/health/ready"),
    _req("meili_down.search_500", "GET", f"{S}/?q=otter", U1),
    _req("meili_down.suggest_degrades", "GET", f"{S}/suggest?q=ott", U1),
    _req("meili_down.advanced_500", "POST", f"{S}/advanced", U1, json={"q": "otter"}),
    _req(
        "meili_down.index_document_500", "POST", f"{S}/index/document", U1, json=DOC_2
    ),
    _req("meili_down.delete_500", "DELETE", f"{S}/index/document/parity-doc-1", U1),
    _act("meili.started", "start_meilisearch"),
    _req("meili_up.health_ready_ok", "GET", "/health/ready"),
    _req("meili_up.search", "GET", f"{S}/?q=otter", BEARER),
    # --- final state -------------------------------------------------------
    _req("analytics.final", "GET", f"{S}/analytics", BEARER),
    _req("metrics.final", "GET", "/metrics"),
]
