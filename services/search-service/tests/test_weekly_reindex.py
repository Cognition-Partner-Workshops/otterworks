import configparser
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests


def test_weekly_job_fetches_every_source_before_any_index_mutation(monkeypatch):
    path = Path(__file__).resolve().parents[3] / "etl/scripts/search_reindex_weekly.py"
    spec = importlib.util.spec_from_file_location("weekly_reindex", path)
    weekly = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(weekly)
    config = configparser.ConfigParser()
    config.read_dict(
        {
            "services": {
                "document_service_url": "http://documents",
                "file_service_url": "http://files",
                "meilisearch_url": "http://search",
                "meilisearch_api_key": "",
            }
        }
    )
    monkeypatch.setenv("FILE_REINDEX_TOKEN", "test-service-credential")
    empty = MagicMock()
    empty.json.return_value = {"documents": []}
    failure = requests.Response()
    failure.status_code = 401
    with (
        patch.object(weekly.configparser, "ConfigParser", return_value=config),
        patch.object(weekly.requests, "get", side_effect=[empty, failure]) as get,
        patch.object(weekly.requests, "delete") as delete,
        patch.object(weekly.requests, "post") as post,
    ):
        with pytest.raises(requests.HTTPError):
            weekly.main()
        delete.assert_not_called()
        post.assert_not_called()
        assert get.call_args.args[0] == "http://files/internal/files/reindex"
        assert (
            get.call_args.kwargs["headers"]["Authorization"]
            == "Bearer test-service-credential"
        )
