"""Unit tests for CustomerDjangoRepository.

Covers:
- Instantiation and interface compliance.
- CRUD operations: get_by_id, list, save, delete.
- Domain look-ups: get_by_document, get_by_email.
- Edge cases: invalid UUID, non-existent records, soft-delete behaviour.
"""

from __future__ import annotations

import uuid

import pytest

from modules.customers.models import Customer, DocumentType
from modules.customers.repositories.django_repository import CustomerDjangoRepository

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Well-known valid documents
# ---------------------------------------------------------------------------
VALID_CPF = "59860184275"
VALID_CPF_2 = "82382537098"
VALID_CNPJ = "11222333000181"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_customer(save: bool = True, **overrides) -> Customer:
    """Create a Customer instance with sane defaults."""
    defaults = {
        "name": "Maria Silva",
        "document": VALID_CPF,
        "document_type": DocumentType.CPF,
        "email": f"{uuid.uuid4().hex[:8]}@example.com",
    }
    defaults.update(overrides)
    customer = Customer(**defaults)
    if save:
        customer.save()
    return customer


@pytest.fixture()
def repo() -> CustomerDjangoRepository:
    return CustomerDjangoRepository()


# ===========================================================================
# Instantiation
# ===========================================================================


class TestRepositoryInstantiation:
    def test_can_instantiate(self, repo):
        assert repo is not None

    def test_is_instance_of_interface(self, repo):
        from modules.customers.repositories.interfaces import ICustomerRepository

        assert isinstance(repo, ICustomerRepository)


# ===========================================================================
# get_by_id
# ===========================================================================


class TestGetById:
    def test_returns_customer_when_found(self, repo):
        customer = _make_customer()
        result = repo.get_by_id(str(customer.id))
        assert result is not None
        assert result.id == customer.id

    def test_returns_none_when_not_found(self, repo):
        fake_id = str(uuid.uuid4())
        assert repo.get_by_id(fake_id) is None

    def test_returns_none_for_invalid_uuid(self, repo):
        assert repo.get_by_id("not-a-uuid") is None

    def test_returns_soft_deleted_customer(self, repo):
        """Repository returns ALL records; service layer handles filtering."""
        customer = _make_customer()
        customer.delete()
        result = repo.get_by_id(str(customer.id))
        assert result is not None
        assert result.is_deleted


# ===========================================================================
# list
# ===========================================================================


class TestList:
    def test_returns_all_customers(self, repo):
        _make_customer(document=VALID_CPF, email="a@test.com")
        _make_customer(document=VALID_CPF_2, email="b@test.com")
        result = repo.list()
        assert len(result) == 2

    def test_returns_empty_list_when_no_customers(self, repo):
        result = repo.list()
        assert len(result) == 0

    def test_filters_by_is_active(self, repo):
        _make_customer(document=VALID_CPF, email="active@test.com", is_active=True)
        _make_customer(document=VALID_CPF_2, email="inactive@test.com", is_active=False)
        result = repo.list(filters={"is_active": True})
        assert len(result) == 1
        assert result[0].is_active is True

    def test_filters_by_name_icontains(self, repo):
        _make_customer(name="Alice Wonder", document=VALID_CPF, email="a@test.com")
        _make_customer(name="Bob Builder", document=VALID_CPF_2, email="b@test.com")
        result = repo.list(filters={"name__icontains": "alice"})
        assert len(result) == 1
        assert result[0].name == "Alice Wonder"

    def test_includes_soft_deleted_in_list(self, repo):
        """objects.all() includes soft-deleted records."""
        customer = _make_customer()
        customer.delete()
        result = repo.list()
        assert len(result) == 1


# ===========================================================================
# save
# ===========================================================================


class TestSave:
    def test_creates_new_customer(self, repo):
        customer = _make_customer(save=False)
        result = repo.save(customer)
        assert result.id is not None
        assert Customer.objects.filter(id=result.id).exists()

    def test_updates_existing_customer(self, repo):
        customer = _make_customer()
        customer.name = "Updated Name"
        result = repo.save(customer)
        refreshed = Customer.objects.get(id=customer.id)
        assert refreshed.name == "Updated Name"
        assert result.name == "Updated Name"

    def test_returns_same_entity(self, repo):
        customer = _make_customer(save=False)
        result = repo.save(customer)
        assert result is customer


# ===========================================================================
# delete
# ===========================================================================


class TestDelete:
    def test_soft_deletes_existing_customer(self, repo):
        customer = _make_customer()
        result = repo.delete(str(customer.id))
        assert result is True
        customer.refresh_from_db()
        assert customer.is_deleted

    def test_returns_false_for_nonexistent(self, repo):
        fake_id = str(uuid.uuid4())
        assert repo.delete(fake_id) is False

    def test_returns_false_for_invalid_uuid(self, repo):
        assert repo.delete("bad-id") is False


# ===========================================================================
# get_by_document
# ===========================================================================


class TestGetByDocument:
    def test_returns_customer_when_found(self, repo):
        customer = _make_customer(document=VALID_CPF)
        result = repo.get_by_document(VALID_CPF)
        assert result is not None
        assert result.id == customer.id

    def test_returns_none_when_not_found(self, repo):
        assert repo.get_by_document("00000000000") is None


# ===========================================================================
# get_by_email
# ===========================================================================


class TestGetByEmail:
    def test_returns_customer_when_found(self, repo):
        customer = _make_customer(email="found@example.com")
        result = repo.get_by_email("found@example.com")
        assert result is not None
        assert result.id == customer.id

    def test_returns_none_when_not_found(self, repo):
        assert repo.get_by_email("ghost@example.com") is None
