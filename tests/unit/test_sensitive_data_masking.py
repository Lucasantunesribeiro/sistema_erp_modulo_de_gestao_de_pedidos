import pytest

pytestmark = pytest.mark.unit


class TestSensitiveDataMasking:
    def test_cpf_masked(self):
        from config.settings import mask_sensitive_data

        event_dict = {"event": "test", "cpf": "123.456.789-00"}
        result = mask_sensitive_data(None, None, event_dict)
        assert "123.456.789-00" not in result["cpf"]
        assert "***MASKED***" in result["cpf"]

    def test_cnpj_masked(self):
        from config.settings import mask_sensitive_data

        event_dict = {"event": "test", "cnpj": "12.345.678/0001-90"}
        result = mask_sensitive_data(None, None, event_dict)
        assert "12.345.678/0001-90" not in result["cnpj"]
        assert "***MASKED***" in result["cnpj"]

    def test_password_masked(self):
        from config.settings import mask_sensitive_data

        event_dict = {"event": "test", "data": "password='s3cret123'"}
        result = mask_sensitive_data(None, None, event_dict)
        assert "s3cret123" not in result["data"]
        assert "***MASKED***" in result["data"]

    def test_token_masked(self):
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
