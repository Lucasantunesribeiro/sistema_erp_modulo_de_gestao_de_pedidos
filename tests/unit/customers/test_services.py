"""Unit tests for CustomerService.

Covers:
- create_customer: happy path, duplicate document (RN-CLI-001),
  duplicate email (RN-CLI-002).
- update_customer: happy path, not found, email collision.
- get_customer: happy path, not found.
- delete_customer: happy path, not found.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from modules.customers.dtos import (
    CreateCustomerDTO,
    DocumentTypeEnum,
    UpdateCustomerDTO,
)
from modules.customers.exceptions import CustomerAlreadyExists, CustomerNotFound
from modules.customers.models import Customer, DocumentType
from modules.customers.services import CustomerService

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Well-known valid documents
# ---------------------------------------------------------------------------
VALID_CPF = "59860184275"
VALID_CNPJ = "11222333000181"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_repo():
    return MagicMock()


@pytest.fixture()
def service(mock_repo):
    return CustomerService(repository=mock_repo)


def _make_customer(**overrides) -> Customer:
    defaults = {
        "name": "João Silva",
        "document": VALID_CPF,
        "document_type": DocumentType.CPF,
        "email": "joao@example.com",
    }
    defaults.update(overrides)
    customer = Customer(**defaults)
    customer.save()
    return customer


# ===========================================================================
# create_customer
# ===========================================================================


class TestCreateCustomer:
    def test_success(self, service, mock_repo):
        mock_repo.get_by_document.return_value = None
        mock_repo.get_by_email.return_value = None
        mock_repo.save.side_effect = lambda c: c

        dto = CreateCustomerDTO(
            name="João Silva",
            document=VALID_CPF,
            document_type=DocumentTypeEnum.CPF,
            email="joao@example.com",
        )
        customer = service.create_customer(dto)

        assert customer.name == "João Silva"
        assert customer.document == VALID_CPF
        assert customer.email == "joao@example.com"
        mock_repo.save.assert_called_once()

    def test_duplicate_document_raises(self, service, mock_repo):
        mock_repo.get_by_document.return_value = _make_customer()

        dto = CreateCustomerDTO(
            name="Duplicate",
            document=VALID_CPF,
            document_type=DocumentTypeEnum.CPF,
            email="other@example.com",
        )
        with pytest.raises(CustomerAlreadyExists, match="Document"):
            service.create_customer(dto)

        mock_repo.save.assert_not_called()

    def test_duplicate_email_raises(self, service, mock_repo):
        mock_repo.get_by_document.return_value = None
        mock_repo.get_by_email.return_value = _make_customer()

        dto = CreateCustomerDTO(
            name="Duplicate",
            document=VALID_CNPJ,
            document_type=DocumentTypeEnum.CNPJ,
            email="joao@example.com",
        )
        with pytest.raises(CustomerAlreadyExists, match="Email"):
            service.create_customer(dto)

        mock_repo.save.assert_not_called()

    def test_sets_optional_fields(self, service, mock_repo):
        mock_repo.get_by_document.return_value = None
        mock_repo.get_by_email.return_value = None
        mock_repo.save.side_effect = lambda c: c

        dto = CreateCustomerDTO(
            name="Test",
            document=VALID_CPF,
            document_type=DocumentTypeEnum.CPF,
            email="test@example.com",
            phone="11999998888",
            address="Rua A, 123",
        )
        customer = service.create_customer(dto)

        assert customer.phone == "11999998888"
        assert customer.address == "Rua A, 123"


# ===========================================================================
# update_customer
# ===========================================================================


class TestUpdateCustomer:
    def test_success(self, service, mock_repo):
        existing = _make_customer()
        mock_repo.get_by_id.return_value = existing
        mock_repo.save.side_effect = lambda c: c

        dto = UpdateCustomerDTO(name="João Atualizado")
        customer = service.update_customer(str(existing.id), dto)

        assert customer.name == "João Atualizado"
        mock_repo.save.assert_called_once()

    def test_not_found_raises(self, service, mock_repo):
        mock_repo.get_by_id.return_value = None

        dto = UpdateCustomerDTO(name="Ghost")
        with pytest.raises(CustomerNotFound):
            service.update_customer("non-existent-id", dto)

    def test_email_collision_raises(self, service, mock_repo):
        existing = _make_customer()
        other = _make_customer(
            document=VALID_CNPJ,
            document_type=DocumentType.CNPJ,
            email="taken@example.com",
        )
        mock_repo.get_by_id.return_value = existing
        mock_repo.get_by_email.return_value = other

        dto = UpdateCustomerDTO(email="taken@example.com")
        with pytest.raises(CustomerAlreadyExists, match="Email"):
            service.update_customer(str(existing.id), dto)

        mock_repo.save.assert_not_called()

    def test_same_email_not_rejected(self, service, mock_repo):
        existing = _make_customer()
        mock_repo.get_by_id.return_value = existing
        mock_repo.save.side_effect = lambda c: c

        dto = UpdateCustomerDTO(email="joao@example.com")
        customer = service.update_customer(str(existing.id), dto)

        assert customer.email == "joao@example.com"
        mock_repo.get_by_email.assert_not_called()

    def test_partial_update_preserves_other_fields(self, service, mock_repo):
        existing = _make_customer(phone="11999998888", address="Rua A")
        mock_repo.get_by_id.return_value = existing
        mock_repo.save.side_effect = lambda c: c

        dto = UpdateCustomerDTO(phone="11888887777")
        customer = service.update_customer(str(existing.id), dto)

        assert customer.phone == "11888887777"
        assert customer.address == "Rua A"
        assert customer.name == "João Silva"

    def test_update_is_active(self, service, mock_repo):
        existing = _make_customer()
        mock_repo.get_by_id.return_value = existing
        mock_repo.save.side_effect = lambda c: c

        dto = UpdateCustomerDTO(is_active=False)
        customer = service.update_customer(str(existing.id), dto)

        assert customer.is_active is False


# ===========================================================================
# get_customer
# ===========================================================================


class TestGetCustomer:
    def test_success(self, service, mock_repo):
        existing = _make_customer()
        mock_repo.get_by_id.return_value = existing

        customer = service.get_customer(str(existing.id))

        assert customer.id == existing.id

    def test_not_found_raises(self, service, mock_repo):
        mock_repo.get_by_id.return_value = None

        with pytest.raises(CustomerNotFound):
            service.get_customer("non-existent-id")


# ===========================================================================
# delete_customer
# ===========================================================================


class TestDeleteCustomer:
    def test_success(self, service, mock_repo):
        existing = _make_customer()
        mock_repo.get_by_id.return_value = existing
        mock_repo.delete.return_value = True

        service.delete_customer(str(existing.id))

        mock_repo.delete.assert_called_once_with(str(existing.id))

    def test_not_found_raises(self, service, mock_repo):
        mock_repo.get_by_id.return_value = None

        with pytest.raises(CustomerNotFound):
            service.delete_customer("non-existent-id")
