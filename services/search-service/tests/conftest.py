"""Pytest fixtures for Search Service tests."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import AppConfig, AuthConfig, MeiliSearchConfig, SQSConfig
from app.main import create_app
from app.services.meilisearch_client import MeiliSearchService


@pytest.fixture()
def app_config() -> AppConfig:
    """Create a test AppConfig with auth disabled."""
    return AppConfig(
        service_name="search-service-test",
        port=8087,
        debug=True,
        log_level="DEBUG",
        meilisearch=MeiliSearchConfig(
            url="http://localhost:7700",
            api_key="",
            documents_index="test-otterworks-documents",
            files_index="test-otterworks-files",
        ),
        sqs=SQSConfig(enabled=False),
        auth=AuthConfig(service_token="", require_auth=False),
    )


@pytest.fixture()
def mock_meilisearch_client() -> MagicMock:
    """Create a mock meilisearch.Client."""
    mock = MagicMock()

    mock_health = {"status": "available"}
    mock.health.return_value = mock_health

    mock_task = MagicMock()
    mock_task.task_uid = 1
    mock_task_result = MagicMock()
    mock_task_result.status = "succeeded"
    mock.wait_for_task.return_value = mock_task_result

    mock_index = MagicMock()
    mock_index.add_documents.return_value = mock_task
    mock_index.delete_document.return_value = mock_task
    mock_index.search.return_value = {"hits": [], "estimatedTotalHits": 0}
    mock.index.return_value = mock_index

    mock.create_index.return_value = mock_task
    mock.delete_index.return_value = mock_task
    mock.get_index.side_effect = None

    return mock


class FlaskStyleResponse:
    """httpx response exposing the Flask test-response API the tests use."""

    def __init__(self, response: httpx.Response) -> None:
        self._response = response

    def __getattr__(self, name: str) -> Any:
        return getattr(self._response, name)

    @property
    def data(self) -> bytes:
        return self._response.content

    def get_data(self, as_text: bool = False) -> bytes | str:
        return self._response.text if as_text else self._response.content

    @property
    def mimetype(self) -> str:
        return self._response.headers.get("content-type", "").split(";", 1)[0].strip().lower()

    @property
    def content_type(self) -> str | None:
        return self._response.headers.get("content-type")

    @property
    def is_json(self) -> bool:
        mt = self.mimetype
        return mt == "application/json" or (mt.startswith("application/") and mt.endswith("+json"))

    def get_json(self, force: bool = False, silent: bool = False) -> Any:
        if not (force or self.is_json):
            return None
        try:
            return json.loads(self._response.content)
        except ValueError:
            if silent:
                return None
            raise


class FlaskStyleClient:
    """TestClient wrapper accepting Flask test-client kwargs (``data=``, ``content_type=``, ...)."""

    def __init__(self, client: TestClient) -> None:
        self._client = client

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)

    def open(
        self,
        path: str,
        method: str = "GET",
        *,
        data: Any = None,
        json: Any = None,
        content_type: str | None = None,
        headers: dict[str, str] | None = None,
        query_string: Any = None,
        follow_redirects: bool = False,
        **kwargs: Any,
    ) -> FlaskStyleResponse:
        request_headers = dict(headers or {})
        if content_type is not None:
            request_headers["Content-Type"] = content_type
        if isinstance(data, (str, bytes)):
            kwargs["content"] = data
        elif data is not None:
            kwargs["data"] = data
        if json is not None:
            kwargs["json"] = json
        if query_string is not None:
            kwargs["params"] = query_string
        response = self._client.request(
            method,
            path,
            headers=request_headers,
            follow_redirects=follow_redirects,
            **kwargs,
        )
        return FlaskStyleResponse(response)

    def get(self, path: str, **kwargs: Any) -> FlaskStyleResponse:
        return self.open(path, "GET", **kwargs)

    def post(self, path: str, **kwargs: Any) -> FlaskStyleResponse:
        return self.open(path, "POST", **kwargs)

    def put(self, path: str, **kwargs: Any) -> FlaskStyleResponse:
        return self.open(path, "PUT", **kwargs)

    def patch(self, path: str, **kwargs: Any) -> FlaskStyleResponse:
        return self.open(path, "PATCH", **kwargs)

    def delete(self, path: str, **kwargs: Any) -> FlaskStyleResponse:
        return self.open(path, "DELETE", **kwargs)

    def head(self, path: str, **kwargs: Any) -> FlaskStyleResponse:
        return self.open(path, "HEAD", **kwargs)

    def options(self, path: str, **kwargs: Any) -> FlaskStyleResponse:
        return self.open(path, "OPTIONS", **kwargs)


@pytest.fixture()
def app(app_config: AppConfig, mock_meilisearch_client: MagicMock) -> Iterator[FastAPI]:
    """Create a FastAPI test app with mocked MeiliSearch.

    The patch stays active for the whole test because the lifespan (entered
    by ``client``) is what constructs the MeiliSearch client.
    """
    with patch("app.services.meilisearch_client.meilisearch.Client") as mock_cls:
        mock_cls.return_value = mock_meilisearch_client
        yield create_app(app_config)


@pytest.fixture()
def client(app: FastAPI) -> Iterator[FlaskStyleClient]:
    """Create a FastAPI TestClient (lifespan running) with a Flask-style API."""
    with TestClient(app, base_url="http://localhost") as test_client:
        yield FlaskStyleClient(test_client)


@pytest.fixture()
def meilisearch_service(app_config: AppConfig, mock_meilisearch_client: MagicMock) -> MeiliSearchService:
    """Create a MeiliSearchService with a mocked client."""
    with patch("app.services.meilisearch_client.meilisearch.Client") as mock_cls:
        mock_cls.return_value = mock_meilisearch_client
        service = MeiliSearchService(app_config.meilisearch)
        return service
