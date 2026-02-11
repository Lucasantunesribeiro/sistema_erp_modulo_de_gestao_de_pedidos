import logging
import uuid

import pytest


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


class TestSensitiveDataMasking:
    def test_cpf_masked_in_log_output(self):
        from config.settings import mask_sensitive_data

        event_dict = {"event": "test", "cpf": "123.456.789-00"}
        result = mask_sensitive_data(None, None, event_dict)
        assert "123.456.789-00" not in result["cpf"]
        assert "***MASKED***" in result["cpf"]

    def test_cnpj_masked_in_log_output(self):
        from config.settings import mask_sensitive_data

        event_dict = {"event": "test", "cnpj": "12.345.678/0001-90"}
        result = mask_sensitive_data(None, None, event_dict)
        assert "12.345.678/0001-90" not in result["cnpj"]
        assert "***MASKED***" in result["cnpj"]

    def test_password_masked_in_log_output(self):
        from config.settings import mask_sensitive_data

        event_dict = {"event": "test", "data": "password='s3cret123'"}
        result = mask_sensitive_data(None, None, event_dict)
        assert "s3cret123" not in result["data"]
        assert "***MASKED***" in result["data"]

    def test_token_masked_in_log_output(self):
        from config.settings import mask_sensitive_data

        event_dict = {"event": "test", "header": "token=abc123xyz"}
        result = mask_sensitive_data(None, None, event_dict)
        assert "abc123xyz" not in result["header"]
        assert "***MASKED***" in result["header"]

    def test_non_sensitive_data_unchanged(self):
        from config.settings import mask_sensitive_data

        event_dict = {"event": "order_created", "order_id": "ORD-001"}
        result = mask_sensitive_data(None, None, event_dict)
        assert result["order_id"] == "ORD-001"
        assert result["event"] == "order_created"
