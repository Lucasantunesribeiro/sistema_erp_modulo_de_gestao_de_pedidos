"""Unit tests for Customer DTOs.

Covers:
- CreateCustomerDTO: validation, sanitisation, frozen immutability.
- CustomerOutputDTO: document masking, from_entity factory.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from modules.customers.dtos import (
    CreateCustomerDTO,
    CustomerOutputDTO,
    DocumentTypeEnum,
)
from modules.customers.models import Customer, DocumentType

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Well-known valid documents
# ---------------------------------------------------------------------------
VALID_CPF = "59860184275"
VALID_CPF_FORMATTED = "598.601.842-75"
VALID_CNPJ = "11222333000181"
VALID_CNPJ_FORMATTED = "11.222.333/0001-81"


# ===========================================================================
# CreateCustomerDTO
# ===========================================================================


class TestCreateCustomerDTOValid:
    def test_create_with_valid_cpf(self):
        dto = CreateCustomerDTO(
            name="João Silva",
            document=VALID_CPF,
            document_type=DocumentTypeEnum.CPF,
            email="joao@example.com",
        )
        assert dto.name == "João Silva"
        assert dto.document == VALID_CPF
        assert dto.document_type == DocumentTypeEnum.CPF

    def test_create_with_valid_cnpj(self):
        dto = CreateCustomerDTO(
            name="Acme Corp",
            document=VALID_CNPJ,
            document_type=DocumentTypeEnum.CNPJ,
            email="acme@example.com",
        )
        assert dto.document == VALID_CNPJ

    def test_optional_fields_default_empty(self):
        dto = CreateCustomerDTO(
            name="Test",
            document=VALID_CPF,
            document_type=DocumentTypeEnum.CPF,
            email="test@example.com",
        )
        assert dto.phone == ""
        assert dto.address == ""

    def test_optional_fields_can_be_set(self):
        dto = CreateCustomerDTO(
            name="Test",
            document=VALID_CPF,
            document_type=DocumentTypeEnum.CPF,
            email="test@example.com",
            phone="11999998888",
            address="Rua A, 123",
        )
        assert dto.phone == "11999998888"
        assert dto.address == "Rua A, 123"


class TestCreateCustomerDTOSanitisation:
    def test_strips_cpf_formatting(self):
        dto = CreateCustomerDTO(
            name="Test",
            document=VALID_CPF_FORMATTED,
            document_type=DocumentTypeEnum.CPF,
            email="test@example.com",
        )
        assert dto.document == VALID_CPF

    def test_strips_cnpj_formatting(self):
        dto = CreateCustomerDTO(
            name="Test",
            document=VALID_CNPJ_FORMATTED,
            document_type=DocumentTypeEnum.CNPJ,
            email="test@example.com",
        )
        assert dto.document == VALID_CNPJ


class TestCreateCustomerDTOValidation:
    def test_invalid_cpf_raises(self):
        with pytest.raises(ValidationError, match="Invalid CPF"):
            CreateCustomerDTO(
                name="Test",
                document="12345678901",
                document_type=DocumentTypeEnum.CPF,
                email="test@example.com",
            )

    def test_invalid_cnpj_raises(self):
        with pytest.raises(ValidationError, match="Invalid CNPJ"):
            CreateCustomerDTO(
                name="Test",
                document="12345678901234",
                document_type=DocumentTypeEnum.CNPJ,
                email="test@example.com",
            )

    def test_invalid_email_raises(self):
        with pytest.raises(ValidationError):
            CreateCustomerDTO(
                name="Test",
                document=VALID_CPF,
                document_type=DocumentTypeEnum.CPF,
                email="not-an-email",
            )

    def test_invalid_document_type_raises(self):
        with pytest.raises(ValidationError):
            CreateCustomerDTO(
                name="Test",
                document=VALID_CPF,
                document_type="INVALID",
                email="test@example.com",
            )


class TestCreateCustomerDTOFrozen:
    def test_is_immutable(self):
        dto = CreateCustomerDTO(
            name="Test",
            document=VALID_CPF,
            document_type=DocumentTypeEnum.CPF,
            email="test@example.com",
        )
        with pytest.raises(ValidationError):
            dto.name = "Changed"


# ===========================================================================
# CustomerOutputDTO
# ===========================================================================


class TestCustomerOutputDTOMasking:
    def test_mask_document_cpf(self):
        assert CustomerOutputDTO.mask_document("59860184275") == "***4275"

    def test_mask_document_cnpj(self):
        assert CustomerOutputDTO.mask_document("11222333000181") == "***0181"

    def test_mask_document_empty(self):
        assert CustomerOutputDTO.mask_document("") == "***????"


class TestCustomerOutputDTOFromEntity:
    def test_from_entity_masks_document(self):
        customer = Customer(
            name="João Silva",
            document=VALID_CPF,
            document_type=DocumentType.CPF,
            email="joao@example.com",
            is_active=True,
        )
        customer.save()
        dto = CustomerOutputDTO.from_entity(customer)
        assert dto.document == "***4275"
        assert dto.name == "João Silva"
        assert dto.id == customer.id
        assert dto.is_active is True

    def test_from_entity_preserves_all_fields(self):
        customer = Customer(
            name="Acme Corp",
            document=VALID_CNPJ,
            document_type=DocumentType.CNPJ,
            email="acme@example.com",
            phone="11999998888",
            address="Rua A, 123",
        )
        customer.save()
        dto = CustomerOutputDTO.from_entity(customer)
        assert dto.email == "acme@example.com"
        assert dto.phone == "11999998888"
        assert dto.address == "Rua A, 123"
        assert dto.document_type == "CNPJ"
        assert dto.created_at is not None
        assert dto.updated_at is not None


class TestCustomerOutputDTOFrozen:
    def test_is_immutable(self):
        customer = Customer(
            name="Test",
            document=VALID_CPF,
            document_type=DocumentType.CPF,
            email="test@example.com",
        )
        customer.save()
        dto = CustomerOutputDTO.from_entity(customer)
        with pytest.raises(ValidationError):
            dto.name = "Changed"
