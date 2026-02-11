"""Unit tests for Customer DRF serializers.

Covers:
- Field presence and read-only constraints.
- Serialization of a Customer instance.
- Deserialization and uniqueness validation.
"""

from __future__ import annotations

import uuid

import pytest

from modules.customers.models import Customer, DocumentType
from modules.customers.serializers import CustomerSerializer

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Well-known valid documents
# ---------------------------------------------------------------------------
VALID_CPF = "59860184275"
VALID_CPF_2 = "82382537098"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_customer(**overrides) -> Customer:
    defaults = {
        "name": "João Silva",
        "document": VALID_CPF,
        "document_type": DocumentType.CPF,
        "email": f"{uuid.uuid4().hex[:8]}@example.com",
    }
    defaults.update(overrides)
    customer = Customer(**defaults)
    customer.save()
    return customer


# ===========================================================================
# Field presence
# ===========================================================================


class TestSerializerFields:
    def test_expected_fields(self):
        serializer = CustomerSerializer()
        expected = {
            "id",
            "name",
            "document",
            "document_type",
            "email",
            "phone",
            "address",
            "is_active",
            "created_at",
            "updated_at",
        }
        assert set(serializer.fields.keys()) == expected

    def test_read_only_fields(self):
        serializer = CustomerSerializer()
        for field_name in ("id", "created_at", "updated_at"):
            assert serializer.fields[field_name].read_only is True


# ===========================================================================
# Serialization (Model -> JSON)
# ===========================================================================


class TestSerialization:
    def test_serializes_customer(self):
        customer = _make_customer()
        data = CustomerSerializer(customer).data
        assert data["id"] == str(customer.id)
        assert data["name"] == "João Silva"
        assert data["document"] == VALID_CPF
        assert data["document_type"] == "CPF"
        assert data["is_active"] is True

    def test_serializes_optional_fields(self):
        customer = _make_customer(phone="11999998888", address="Rua A, 123")
        data = CustomerSerializer(customer).data
        assert data["phone"] == "11999998888"
        assert data["address"] == "Rua A, 123"


# ===========================================================================
# Deserialization (JSON -> validated data)
# ===========================================================================


class TestDeserialization:
    def test_valid_input(self):
        payload = {
            "name": "Maria Souza",
            "document": VALID_CPF_2,
            "document_type": "CPF",
            "email": "maria@example.com",
        }
        serializer = CustomerSerializer(data=payload)
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["name"] == "Maria Souza"

    def test_missing_required_field(self):
        payload = {"name": "No Email"}
        serializer = CustomerSerializer(data=payload)
        assert not serializer.is_valid()
        assert "document" in serializer.errors

    def test_duplicate_document_rejected(self):
        _make_customer(document=VALID_CPF, email="first@example.com")
        payload = {
            "name": "Duplicate",
            "document": VALID_CPF,
            "document_type": "CPF",
            "email": "second@example.com",
        }
        serializer = CustomerSerializer(data=payload)
        assert not serializer.is_valid()
        assert "document" in serializer.errors

    def test_duplicate_email_rejected(self):
        _make_customer(document=VALID_CPF, email="taken@example.com")
        payload = {
            "name": "Duplicate",
            "document": VALID_CPF_2,
            "document_type": "CPF",
            "email": "taken@example.com",
        }
        serializer = CustomerSerializer(data=payload)
        assert not serializer.is_valid()
        assert "email" in serializer.errors
