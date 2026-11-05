"""Tests for health and metrics endpoints."""

from __future__ import annotations

import subprocess
import sys


class TestHealthEndpoint:
    """Tests for GET /health (liveness)."""

    def test_health_returns_200(self, client):
        """Liveness always returns 200 without contacting dependencies."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "alive"
        assert data["service"] == "search-service"


class TestReadinessEndpoint:
    """Tests for GET /health/ready."""

    def test_ready_when_meilisearch_connected(self, client, mock_meilisearch_client):
        """Readiness returns 200 when MeiliSearch is reachable."""
        mock_meilisearch_client.health.return_value = {"status": "available"}
        response = client.get("/health/ready")
        assert response.status_code == 200
        data = response.get_json()
        assert data["ready"] is True

    def test_not_ready_when_meilisearch_disconnected(self, client, mock_meilisearch_client):
        """Readiness returns 503 when MeiliSearch is unreachable."""
        mock_meilisearch_client.health.side_effect = Exception("unreachable")
        response = client.get("/health/ready")
        assert response.status_code == 503
        data = response.get_json()
        assert data["ready"] is False


class TestMetricsEndpoint:
    """Tests for GET /metrics."""

    def test_metrics_returns_prometheus_format(self, client):
        """Metrics endpoint returns Prometheus text format."""
        response = client.get("/metrics")
        assert response.status_code == 200
        assert b"search_service" in response.data

    def test_metrics_aggregates_worker_counters(self, client, monkeypatch, tmp_path):
        monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", str(tmp_path))
        for count in (113, 166):
            subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "from app.api.health import REQUEST_COUNT; "
                        "REQUEST_COUNT.labels('GET', '/api/v1/search/suggest', '500')"
                        f".inc({count})"
                    ),
                ],
                check=True,
            )

        for _ in range(3):
            response = client.get("/metrics")
            assert response.status_code == 200
            assert (
                b'search_service_requests_total{endpoint="/api/v1/search/suggest",'
                b'method="GET",status="500"} 279.0'
            ) in response.data

    def test_metrics_with_no_worker_samples(self, client, monkeypatch, tmp_path):
        monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", str(tmp_path))
        response = client.get("/metrics")
        assert response.status_code == 200
        assert b"search_service_requests_total" not in response.data
