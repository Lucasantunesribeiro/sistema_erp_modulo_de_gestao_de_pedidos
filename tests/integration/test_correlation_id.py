import logging
import uuid

import pytest

pytestmark = pytest.mark.integration


class TestCorrelationIdMiddleware:
    def test_returns_provided_request_id(self, client):
        custom_id = "my-custom-request-id-123"
        response = client.get("/health", HTTP_X_REQUEST_ID=custom_id)
        assert response["X-Request-ID"] == custom_id

    def test_generates_uuid_when_no_request_id(self, client):
        response = client.get("/health")
        request_id = response["X-Request-ID"]
        parsed = uuid.UUID(request_id, version=4)
        assert str(parsed) == request_id

    def test_correlation_id_in_logs(self, client, caplog):
        custom_id = "log-test-correlation-456"
        with caplog.at_level(logging.INFO):
            client.get("/health", HTTP_X_REQUEST_ID=custom_id)
        found = any(custom_id in record.getMessage() for record in caplog.records)
        assert found, (
            f"correlation_id '{custom_id}' not found in log records: "
            f"{[r.getMessage() for r in caplog.records]}"
        )
