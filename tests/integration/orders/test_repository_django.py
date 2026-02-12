"""Integration tests for OrderDjangoRepository.

Covers:
- Create success: order + items persisted atomically.
- Create atomicity: forced error rolls back entire aggregate.
- Read performance: get_by_id loads relations without N+1 queries.
- Locking: get_for_update returns order correctly.
- History: add_history inserts OrderStatusHistory record.
- Idempotency key lookup.
- List with filters.
- Soft delete.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest

from modules.customers.models import Customer, DocumentType
from modules.orders.constants import OrderStatus
from modules.orders.models import Order, OrderItem, OrderStatusHistory
from modules.orders.repositories.django_repository import OrderDjangoRepository
from modules.products.models import Product, ProductStatus

pytestmark = pytest.mark.integration

VALID_CPF = "59860184275"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def repo():
    return OrderDjangoRepository()


@pytest.fixture()
def customer():
    return Customer.objects.create(
        name="Repo Test Customer",
        document=VALID_CPF,
        document_type=DocumentType.CPF,
        email="repo-test@example.com",
        is_active=True,
    )


@pytest.fixture()
def product_a():
    return Product.objects.create(
        sku="REPO-A",
        name="Repo Product A",
        price=Decimal("10.00"),
        stock_quantity=100,
        status=ProductStatus.ACTIVE,
    )


@pytest.fixture()
def product_b():
    return Product.objects.create(
        sku="REPO-B",
        name="Repo Product B",
        price=Decimal("25.50"),
        stock_quantity=50,
        status=ProductStatus.ACTIVE,
    )


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
        "notes": "Integration test order",
    }


@pytest.fixture()
def created_order(repo, order_data):
    return repo.create(order_data)


# ===========================================================================
# CREATE
# ===========================================================================


class TestOrderRepoCreate:
    def test_create_persists_order(self, repo, order_data, customer):
        order = repo.create(order_data)

        assert order.pk is not None
        assert order.customer_id == customer.id
        assert order.status == OrderStatus.PENDING
        assert order.notes == "Integration test order"
        assert order.order_number.startswith("ORD-")

    def test_create_persists_items(self, repo, order_data, product_a, product_b):
        order = repo.create(order_data)

        items = list(order.items.all())
        assert len(items) == 2

        item_a = next(i for i in items if i.product_id == product_a.id)
        assert item_a.quantity == 2
        assert item_a.unit_price == Decimal("10.00")
        assert item_a.subtotal == Decimal("20.00")

        item_b = next(i for i in items if i.product_id == product_b.id)
        assert item_b.quantity == 1
        assert item_b.unit_price == Decimal("25.50")

    def test_create_calculates_total(self, repo, order_data):
        order = repo.create(order_data)
        assert order.total_amount == Decimal("45.50")

    def test_create_with_idempotency_key(self, repo, order_data):
        order_data["idempotency_key"] = "test-idem-key-123"
        order = repo.create(order_data)
        assert order.idempotency_key == "test-idem-key-123"

    def test_create_atomicity_rolls_back_on_item_failure(self, repo, order_data):
        """If an item save fails, the entire order must be rolled back."""
        original_count = Order.objects.count()

        with patch.object(OrderItem, "save", side_effect=RuntimeError("forced error")):
            with pytest.raises(RuntimeError, match="forced error"):
                repo.create(order_data)

        assert Order.objects.count() == original_count
        assert OrderItem.objects.count() == 0


# ===========================================================================
# READ
# ===========================================================================


class TestOrderRepoRead:
    def test_get_by_id_returns_order(self, repo, created_order):
        order = repo.get_by_id(str(created_order.id))
        assert order is not None
        assert order.id == created_order.id

    def test_get_by_id_eager_loads_items(self, repo, created_order):
        order = repo.get_by_id(str(created_order.id))
        # Access items without triggering additional queries
        items = list(order.items.all())
        assert len(items) == 2

    def test_get_by_id_eager_loads_customer(self, repo, created_order):
        order = repo.get_by_id(str(created_order.id))
        # select_related ensures customer is loaded
        assert order.customer.name == "Repo Test Customer"

    def test_get_by_id_returns_none_for_missing(self, repo):
        result = repo.get_by_id("00000000-0000-0000-0000-000000000000")
        assert result is None

    def test_get_by_id_returns_none_for_invalid_uuid(self, repo):
        result = repo.get_by_id("not-a-uuid")
        assert result is None

    def test_get_by_id_no_n_plus_one(
        self, repo, created_order, django_assert_num_queries
    ):
        """get_by_id should load order + customer + items + products + history
        in a bounded number of queries (not N+1)."""
        with django_assert_num_queries(4):
            # 1: SELECT order JOIN customer (select_related)
            # 2: SELECT order_items (prefetch_related items__product - items)
            # 3: SELECT products (prefetch_related items__product - products)
            # 4: SELECT status_history (prefetch_related status_history)
            order = repo.get_by_id(str(created_order.id))
            # Force evaluation of prefetched relations
            list(order.items.all())
            for item in order.items.all():
                _ = item.product.name
            list(order.status_history.all())

    def test_list_returns_all_orders(self, repo, created_order):
        orders = repo.list()
        assert len(orders) == 1
        assert orders[0].id == created_order.id

    def test_list_filter_by_status(self, repo, created_order):
        orders = repo.list(filters={"status": OrderStatus.PENDING})
        assert len(orders) == 1

        orders = repo.list(filters={"status": OrderStatus.CONFIRMED})
        assert len(orders) == 0

    def test_list_filter_by_customer(self, repo, created_order, customer):
        orders = repo.list(filters={"customer_id": customer.id})
        assert len(orders) == 1


# ===========================================================================
# UPDATE
# ===========================================================================


class TestOrderRepoUpdate:
    def test_update_changes_fields(self, repo, created_order):
        updated = repo.update(created_order.id, {"notes": "Updated notes"})
        assert updated.notes == "Updated notes"

    def test_update_nonexistent_raises(self, repo):
        from uuid import uuid4

        with pytest.raises(Order.DoesNotExist):
            repo.update(uuid4(), {"notes": "no order"})


# ===========================================================================
# LOCKING
# ===========================================================================


class TestOrderRepoLocking:
    def test_get_for_update_returns_order(self, repo, created_order):
        order = repo.get_for_update(str(created_order.id))
        assert order is not None
        assert order.id == created_order.id

    def test_get_for_update_returns_none_for_missing(self, repo):
        result = repo.get_for_update("00000000-0000-0000-0000-000000000000")
        assert result is None

    def test_get_for_update_returns_none_for_invalid_uuid(self, repo):
        result = repo.get_for_update("not-a-uuid")
        assert result is None

    def test_get_for_update_eager_loads_items(self, repo, created_order):
        order = repo.get_for_update(str(created_order.id))
        items = list(order.items.all())
        assert len(items) == 2


# ===========================================================================
# HISTORY
# ===========================================================================


class TestOrderRepoHistory:
    def test_add_history_creates_record(self, repo, created_order):
        history = repo.add_history(
            order_id=created_order.id,
            status=OrderStatus.CONFIRMED,
            notes="Test transition",
        )

        assert history.pk is not None
        assert history.order_id == created_order.id
        assert history.old_status == OrderStatus.PENDING
        assert history.new_status == OrderStatus.CONFIRMED
        assert history.notes == "Test transition"

    def test_add_history_with_explicit_old_status(self, repo, created_order):
        history = repo.add_history(
            order_id=created_order.id,
            status=OrderStatus.CONFIRMED,
            old_status=OrderStatus.PENDING,
            notes="Explicit old",
        )
        assert history.old_status == OrderStatus.PENDING

    def test_add_history_persists_in_db(self, repo, created_order):
        repo.add_history(
            order_id=created_order.id,
            status=OrderStatus.CONFIRMED,
        )
        count = OrderStatusHistory.objects.filter(order_id=created_order.id).count()
        assert count == 1


# ===========================================================================
# IDEMPOTENCY KEY
# ===========================================================================


class TestOrderRepoIdempotencyKey:
    def test_get_by_idempotency_key_returns_order(self, repo, order_data):
        order_data["idempotency_key"] = "unique-key-abc"
        order = repo.create(order_data)

        found = repo.get_by_idempotency_key("unique-key-abc")
        assert found is not None
        assert found.id == order.id

    def test_get_by_idempotency_key_returns_none_for_missing(self, repo):
        result = repo.get_by_idempotency_key("nonexistent-key")
        assert result is None


# ===========================================================================
# SAVE / DELETE
# ===========================================================================


class TestOrderRepoSaveDelete:
    def test_save_persists_entity(self, repo, created_order):
        created_order.notes = "Saved via save()"
        saved = repo.save(created_order)
        assert saved.notes == "Saved via save()"

        refreshed = Order.objects.get(id=created_order.id)
        assert refreshed.notes == "Saved via save()"

    def test_delete_soft_deletes(self, repo, created_order):
        result = repo.delete(str(created_order.id))
        assert result is True

        # Soft-deleted: still in DB but deleted_at is set
        # objects manager is unfiltered, so we can still get it
        order = Order.objects.get(id=created_order.id)
        assert order.deleted_at is not None

    def test_delete_nonexistent_returns_false(self, repo):
        result = repo.delete("00000000-0000-0000-0000-000000000000")
        assert result is False
