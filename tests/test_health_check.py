import pytest
from django.test import Client


class TestHealthCheck:
    def test_health_check_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "services" in data

    def test_health_check_reports_database_status(self, client):
        response = client.get("/health")
        data = response.json()
        assert data["services"]["database"]["status"] == "up"
        assert "response_time_ms" in data["services"]["database"]

    def test_health_check_reports_cache_status(self, client):
        response = client.get("/health")
        data = response.json()
        assert data["services"]["cache"]["status"] == "up"
        assert "response_time_ms" in data["services"]["cache"]
