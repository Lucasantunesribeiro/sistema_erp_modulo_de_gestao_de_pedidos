"""Unit tests for OrderService.

Covers:
- Order creation with stock reservation (RN-EST-001/002/003/004).
- Customer validation (RN-CLI-003).
- Product validation (RN-PRO-002).
- Status transitions (RN-PED-001).
- History recording (RN-PED-002/003).
- Cancellation with stock release (RN-EST-005/006).
- Atomicity: partial failure rolls back all stock.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from modules.customers.models import Customer, DocumentType
from modules.orders.constants import OrderStatus
from modules.orders.dtos import CreateOrderDTO, CreateOrderItemDTO
from modules.orders.exceptions import (
    CustomerNotFound,
    InactiveCustomer,
    InactiveProduct,
    InsufficientStock,
    InvalidOrderStatus,
    OrderNotFound,
    ProductNotFound,
)
from modules.orders.models import OrderStatusHistory
from modules.orders.repositories.django_repository import OrderDjangoRepository
from modules.orders.services import OrderService
from modules.products.models import Product, ProductStatus
from modules.products.repositories.django_repository import ProductDjangoRepository

pytestmark = pytest.mark.unit

VALID_CPF = "59860184275"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def customer():
    return Customer.objects.create(
        name="Order Test Customer",
        document=VALID_CPF,
        document_type=DocumentType.CPF,
        email="order-svc@example.com",
        is_active=True,
    )


@pytest.fixture()
def inactive_customer():
    return Customer.objects.create(
        name="Inactive Customer",
        document="11222333000181",
        document_type=DocumentType.CNPJ,
        email="inactive@example.com",
        is_active=False,
    )


@pytest.fixture()
def product_a():
    return Product.objects.create(
        sku="SVC-PROD-A",
        name="Service Product A",
        price=Decimal("10.00"),
        stock_quantity=100,
        status=ProductStatus.ACTIVE,
    )


@pytest.fixture()
def product_b():
    return Product.objects.create(
        sku="SVC-PROD-B",
        name="Service Product B",
        price=Decimal("25.50"),
        stock_quantity=50,
        status=ProductStatus.ACTIVE,
    )


@pytest.fixture()
def inactive_product():
    return Product.objects.create(
        sku="SVC-INACTIVE",
        name="Inactive Product",
        price=Decimal("5.00"),
        stock_quantity=10,
        status=ProductStatus.INACTIVE,
    )


@pytest.fixture()
def low_stock_product():
    return Product.objects.create(
        sku="SVC-LOW",
        name="Low Stock Product",
        price=Decimal("15.00"),
        stock_quantity=2,
        status=ProductStatus.ACTIVE,
    )


@pytest.fixture()
def service():
    from modules.customers.repositories.django_repository import (
        CustomerDjangoRepository,
    )

    return OrderService(
        order_repository=OrderDjangoRepository(),
        customer_repository=CustomerDjangoRepository(),
        product_repository=ProductDjangoRepository(),
    )


@pytest.fixture()
def order_dto(customer, product_a, product_b):
    return CreateOrderDTO(
        customer_id=customer.id,
        items=[
            CreateOrderItemDTO(product_id=product_a.id, quantity=2),
            CreateOrderItemDTO(product_id=product_b.id, quantity=1),
        ],
        notes="Test order",
    )


# ===========================================================================
# create_order — Happy Path
# ===========================================================================


class TestCreateOrderSuccess:
    def test_creates_order_with_items(self, service, order_dto):
        order = service.create_order(order_dto)

        assert order is not None
        assert order.status == OrderStatus.PENDING
        assert order.order_number.startswith("ORD-")
        assert len(order.items.all()) == 2

    def test_calculates_total_from_product_prices(self, service, order_dto):
        order = service.create_order(order_dto)

        # 2 * 10.00 + 1 * 25.50 = 45.50
        assert order.total_amount == Decimal("45.50")

    def test_snapshots_current_product_price(self, service, order_dto):
        order = service.create_order(order_dto)
        items = list(order.items.all().order_by("unit_price"))

        assert items[0].unit_price == Decimal("10.00")
        assert items[1].unit_price == Decimal("25.50")

    def test_deducts_stock(self, service, order_dto, product_a, product_b):
        service.create_order(order_dto)

        product_a.refresh_from_db()
        product_b.refresh_from_db()
        assert product_a.stock_quantity == 98  # 100 - 2
        assert product_b.stock_quantity == 49  # 50 - 1

    def test_records_initial_history(self, service, order_dto):
        order = service.create_order(order_dto)
        history = list(order.status_history.all())

        assert len(history) == 1
        assert history[0].new_status == OrderStatus.PENDING
        assert history[0].notes == "Order created"

    def test_stores_notes(self, service, order_dto):
        order = service.create_order(order_dto)
        assert order.notes == "Test order"


# ===========================================================================
# create_order — Validation Failures
# ===========================================================================


class TestCreateOrderCustomerValidation:
    def test_customer_not_found_raises(self, service, product_a):
        dto = CreateOrderDTO(
            customer_id=uuid4(),
            items=[CreateOrderItemDTO(product_id=product_a.id, quantity=1)],
        )
        with pytest.raises(CustomerNotFound):
            service.create_order(dto)

    def test_inactive_customer_raises(self, service, inactive_customer, product_a):
        dto = CreateOrderDTO(
            customer_id=inactive_customer.id,
            items=[CreateOrderItemDTO(product_id=product_a.id, quantity=1)],
        )
        with pytest.raises(InactiveCustomer):
            service.create_order(dto)


class TestCreateOrderProductValidation:
    def test_product_not_found_raises(self, service, customer):
        dto = CreateOrderDTO(
            customer_id=customer.id,
            items=[CreateOrderItemDTO(product_id=uuid4(), quantity=1)],
        )
        with pytest.raises(ProductNotFound):
            service.create_order(dto)

    def test_inactive_product_raises(self, service, customer, inactive_product):
        dto = CreateOrderDTO(
            customer_id=customer.id,
            items=[
                CreateOrderItemDTO(product_id=inactive_product.id, quantity=1),
            ],
        )
        with pytest.raises(InactiveProduct):
            service.create_order(dto)


class TestCreateOrderStockValidation:
    def test_insufficient_stock_raises(self, service, customer, low_stock_product):
        dto = CreateOrderDTO(
            customer_id=customer.id,
            items=[
                CreateOrderItemDTO(product_id=low_stock_product.id, quantity=5),
            ],
        )
        with pytest.raises(InsufficientStock):
            service.create_order(dto)

    def test_atomicity_partial_failure_rolls_back_stock(
        self, service, customer, product_a, low_stock_product
    ):
        """RN-EST-002: If one item fails, all stock is rolled back."""
        dto = CreateOrderDTO(
            customer_id=customer.id,
            items=[
                CreateOrderItemDTO(product_id=product_a.id, quantity=5),
                CreateOrderItemDTO(product_id=low_stock_product.id, quantity=10),
            ],
        )
        with pytest.raises(InsufficientStock):
            service.create_order(dto)

        # Stock must remain untouched
        product_a.refresh_from_db()
        low_stock_product.refresh_from_db()
        assert product_a.stock_quantity == 100
        assert low_stock_product.stock_quantity == 2


# ===========================================================================
# update_status
# ===========================================================================


class TestUpdateStatus:
    def test_valid_transition(self, service, order_dto):
        order = service.create_order(order_dto)
        updated = service.update_status(order.id, OrderStatus.CONFIRMED)

        assert updated.status == OrderStatus.CONFIRMED

    def test_records_history(self, service, order_dto):
        order = service.create_order(order_dto)
        service.update_status(
            order.id, OrderStatus.CONFIRMED, notes="Approved by admin"
        )
        history = OrderStatusHistory.objects.filter(order=order).order_by("created_at")

        # 1 from creation + 1 from status update
        assert history.count() == 2
        last = history.last()
        assert last.old_status == OrderStatus.PENDING
        assert last.new_status == OrderStatus.CONFIRMED
        assert last.notes == "Approved by admin"

    def test_invalid_transition_raises(self, service, order_dto):
        order = service.create_order(order_dto)

        with pytest.raises(InvalidOrderStatus, match="Cannot transition"):
            service.update_status(order.id, OrderStatus.SHIPPED)

    def test_order_not_found_raises(self, service):
        with pytest.raises(OrderNotFound):
            service.update_status(uuid4(), OrderStatus.CONFIRMED)

    def test_full_lifecycle(self, service, order_dto):
        order = service.create_order(order_dto)
        order = service.update_status(order.id, OrderStatus.CONFIRMED)
        order = service.update_status(order.id, OrderStatus.SEPARATED)
        order = service.update_status(order.id, OrderStatus.SHIPPED)
        order = service.update_status(order.id, OrderStatus.DELIVERED)

        assert order.status == OrderStatus.DELIVERED

        # Cannot transition from DELIVERED
        with pytest.raises(InvalidOrderStatus):
            service.update_status(order.id, OrderStatus.CANCELLED)


# ===========================================================================
# cancel_order
# ===========================================================================


class TestCancelOrder:
    def test_cancel_pending_releases_stock(
        self, service, order_dto, product_a, product_b
    ):
        order = service.create_order(order_dto)

        # Stock after creation
        product_a.refresh_from_db()
        product_b.refresh_from_db()
        assert product_a.stock_quantity == 98
        assert product_b.stock_quantity == 49

        service.cancel_order(order.id, notes="Customer request")

        # Stock restored
        product_a.refresh_from_db()
        product_b.refresh_from_db()
        assert product_a.stock_quantity == 100
        assert product_b.stock_quantity == 50

    def test_cancel_confirmed_releases_stock(
        self, service, order_dto, product_a, product_b
    ):
        order = service.create_order(order_dto)
        service.update_status(order.id, OrderStatus.CONFIRMED)

        service.cancel_order(order.id)

        product_a.refresh_from_db()
        product_b.refresh_from_db()
        assert product_a.stock_quantity == 100
        assert product_b.stock_quantity == 50

    def test_cancel_records_history(self, service, order_dto):
        order = service.create_order(order_dto)
        cancelled = service.cancel_order(order.id, notes="Out of stock")

        assert cancelled.status == OrderStatus.CANCELLED
        history = list(cancelled.status_history.all())
        cancel_record = [h for h in history if h.new_status == OrderStatus.CANCELLED]
        assert len(cancel_record) == 1
        assert cancel_record[0].notes == "Out of stock"

    def test_cancel_shipped_raises(self, service, order_dto):
        order = service.create_order(order_dto)
        service.update_status(order.id, OrderStatus.CONFIRMED)
        service.update_status(order.id, OrderStatus.SEPARATED)
        service.update_status(order.id, OrderStatus.SHIPPED)

        with pytest.raises(InvalidOrderStatus, match="Cannot cancel"):
            service.cancel_order(order.id)

    def test_cancel_not_found_raises(self, service):
        with pytest.raises(OrderNotFound):
            service.cancel_order(uuid4())


# ===========================================================================
# Queries
# ===========================================================================


class TestGetOrder:
    def test_returns_order(self, service, order_dto):
        created = service.create_order(order_dto)
        order = service.get_order(str(created.id))

        assert order.id == created.id

    def test_not_found_raises(self, service):
        with pytest.raises(OrderNotFound):
            service.get_order(str(uuid4()))


class TestListOrders:
    def test_returns_all_orders(self, service, order_dto):
        service.create_order(order_dto)
        orders = service.list_orders()
        assert len(orders) == 1

    def test_filters_by_status(self, service, order_dto):
        service.create_order(order_dto)
        orders = service.list_orders({"status": OrderStatus.PENDING})
        assert len(orders) == 1

        orders = service.list_orders({"status": OrderStatus.CONFIRMED})
        assert len(orders) == 0
