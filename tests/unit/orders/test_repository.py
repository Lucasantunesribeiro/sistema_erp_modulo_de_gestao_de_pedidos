"""Unit tests for OrderDjangoRepository.

Covers:
- Aggregate creation (Order + OrderItems) atomically.
- Read with prefetch_related (N+1 prevention).
- Status history tracking.
- Idempotency key look-up.
- Update with select_for_update.
- Soft delete.
- Edge cases (invalid UUIDs, non-existent orders).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from modules.customers.models import Customer, DocumentType
from modules.orders.constants import OrderStatus
from modules.orders.models import Order, OrderItem, OrderStatusHistory
from modules.orders.repositories.django_repository import OrderDjangoRepository
from modules.orders.repositories.interfaces import IOrderRepository
from modules.products.models import Product

pytestmark = pytest.mark.unit

VALID_CPF = "59860184275"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def customer():
    return Customer.objects.create(
        name="Test Customer",
        document=VALID_CPF,
        document_type=DocumentType.CPF,
        email="test@example.com",
    )


@pytest.fixture()
def product_a():
    return Product.objects.create(
        sku="PROD-A",
        name="Product A",
        price=Decimal("10.00"),
        stock_quantity=100,
    )


@pytest.fixture()
def product_b():
    return Product.objects.create(
        sku="PROD-B",
        name="Product B",
        price=Decimal("25.50"),
        stock_quantity=50,
    )


@pytest.fixture()
def repo():
    return OrderDjangoRepository()


@pytest.fixture()
def order_data(customer, product_a, product_b):
    return {
        "customer_id": customer.id,
        "items": [
            {
                "product_id": product_a.id,
                "quantity": 2,
                "unit_price": product_a.price,
            },
            {
                "product_id": product_b.id,
                "quantity": 1,
                "unit_price": product_b.price,
            },
        ],
        "notes": "Test order",
    }


# ===========================================================================
# Instantiation
# ===========================================================================


class TestRepositoryInstantiation:
    def test_can_instantiate(self):
        repo = OrderDjangoRepository()
        assert repo is not None

    def test_is_instance_of_interface(self):
        repo = OrderDjangoRepository()
        assert isinstance(repo, IOrderRepository)


# ===========================================================================
# create
# ===========================================================================


class TestCreate:
    def test_creates_order_with_items(self, repo, order_data):
        order = repo.create(order_data)

        assert order.id is not None
        assert order.order_number.startswith("ORD-")
        assert order.status == OrderStatus.PENDING
        assert order.notes == "Test order"
        assert OrderItem.objects.filter(order=order).count() == 2

    def test_calculates_total_amount(self, repo, order_data):
        order = repo.create(order_data)

        # 2 * 10.00 + 1 * 25.50 = 45.50
        expected_total = Decimal("45.50")
        assert order.total_amount == expected_total

    def test_stores_idempotency_key(self, repo, order_data):
        order_data["idempotency_key"] = "idem-key-123"
        order = repo.create(order_data)

        assert order.idempotency_key == "idem-key-123"

    def test_items_snapshot_unit_price(self, repo, order_data):
        order = repo.create(order_data)
        items = OrderItem.objects.filter(order=order).order_by("created_at")

        assert items[0].unit_price == Decimal("10.00")
        assert items[1].unit_price == Decimal("25.50")

    def test_items_calculate_subtotal(self, repo, order_data):
        order = repo.create(order_data)
        items = OrderItem.objects.filter(order=order).order_by("created_at")

        assert items[0].subtotal == Decimal("20.00")  # 2 * 10.00
        assert items[1].subtotal == Decimal("25.50")  # 1 * 25.50


# ===========================================================================
# get_by_id
# ===========================================================================


class TestGetById:
    def test_returns_order_with_prefetch(self, repo, order_data):
        created = repo.create(order_data)
        order = repo.get_by_id(str(created.id))

        assert order is not None
        assert order.id == created.id
        # prefetch_related should have loaded items
        assert len(order.items.all()) == 2

    def test_returns_none_when_not_found(self, repo):
        result = repo.get_by_id("00000000-0000-0000-0000-000000000000")
        assert result is None

    def test_returns_none_for_invalid_uuid(self, repo):
        result = repo.get_by_id("not-a-uuid")
        assert result is None


# ===========================================================================
# list
# ===========================================================================


class TestList:
    def test_returns_all_orders(self, repo, order_data):
        repo.create(order_data)
        repo.create(order_data)
        results = repo.list()
        assert len(results) == 2

    def test_returns_empty_list_when_no_orders(self, repo):
        results = repo.list()
        assert len(results) == 0

    def test_filters_by_status(self, repo, order_data):
        repo.create(order_data)
        results = repo.list({"status": OrderStatus.PENDING})
        assert len(results) == 1

        results = repo.list({"status": OrderStatus.CONFIRMED})
        assert len(results) == 0

    def test_filters_by_customer_id(self, repo, order_data, customer):
        repo.create(order_data)
        results = repo.list({"customer_id": customer.id})
        assert len(results) == 1


# ===========================================================================
# update
# ===========================================================================


class TestUpdate:
    def test_updates_order_fields(self, repo, order_data):
        order = repo.create(order_data)
        updated = repo.update(order.id, {"status": OrderStatus.CONFIRMED})

        assert updated.status == OrderStatus.CONFIRMED

    def test_update_nonexistent_raises(self, repo):
        from uuid import UUID

        fake_id = UUID("00000000-0000-0000-0000-000000000000")
        with pytest.raises(Order.DoesNotExist):
            repo.update(fake_id, {"status": OrderStatus.CONFIRMED})


# ===========================================================================
# add_history
# ===========================================================================


class TestAddHistory:
    def test_creates_history_record(self, repo, order_data):
        order = repo.create(order_data)
        history = repo.add_history(
            order_id=order.id,
            status=OrderStatus.CONFIRMED,
            notes="Confirmed by admin",
        )

        assert history.id is not None
        assert history.order_id == order.id
        assert history.old_status == OrderStatus.PENDING
        assert history.new_status == OrderStatus.CONFIRMED
        assert history.notes == "Confirmed by admin"

    def test_history_count_increments(self, repo, order_data):
        order = repo.create(order_data)
        repo.add_history(order.id, OrderStatus.CONFIRMED)
        repo.add_history(order.id, OrderStatus.SEPARATED)

        count = OrderStatusHistory.objects.filter(order=order).count()
        assert count == 3


# ===========================================================================
# get_by_idempotency_key
# ===========================================================================


class TestGetByIdempotencyKey:
    def test_returns_order_when_found(self, repo, order_data):
        order_data["idempotency_key"] = "unique-key-abc"
        created = repo.create(order_data)
        result = repo.get_by_idempotency_key("unique-key-abc")

        assert result is not None
        assert result.id == created.id

    def test_returns_none_when_not_found(self, repo):
        result = repo.get_by_idempotency_key("nonexistent-key")
        assert result is None


# ===========================================================================
# save / delete (IRepository contract)
# ===========================================================================


class TestSave:
    def test_saves_order(self, repo, customer):
        order = Order(customer=customer)
        saved = repo.save(order)
        assert saved.id is not None
        assert Order.objects.filter(id=saved.id).exists()


class TestDelete:
    def test_soft_deletes_order(self, repo, order_data):
        order = repo.create(order_data)
        result = repo.delete(str(order.id))
        assert result is True
        order.refresh_from_db()
        assert order.deleted_at is not None

    def test_returns_false_for_nonexistent(self, repo):
        result = repo.delete("00000000-0000-0000-0000-000000000000")
        assert result is False
