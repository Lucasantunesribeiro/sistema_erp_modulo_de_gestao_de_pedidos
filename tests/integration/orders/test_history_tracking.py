"""Integration tests for automatic OrderStatusHistory tracking."""

from __future__ import annotations

from decimal import Decimal

import pytest

from modules.customers.models import Customer, DocumentType
from modules.customers.repositories.django_repository import CustomerDjangoRepository
from modules.orders.constants import OrderStatus
from modules.orders.dtos import CreateOrderDTO, CreateOrderItemDTO
from modules.orders.models import Order, OrderStatusHistory
from modules.orders.repositories.django_repository import OrderDjangoRepository
from modules.orders.services import OrderService
from modules.products.models import Product, ProductStatus
from modules.products.repositories.django_repository import ProductDjangoRepository

pytestmark = pytest.mark.integration

VALID_CPF = "59860184275"


@pytest.fixture()
def service():
    return OrderService(
        order_repository=OrderDjangoRepository(),
        customer_repository=CustomerDjangoRepository(),
        product_repository=ProductDjangoRepository(),
    )


@pytest.fixture()
def customer():
    return Customer.objects.create(
        name="History Customer",
        document=VALID_CPF,
        document_type=DocumentType.CPF,
        email="history@example.com",
        is_active=True,
    )


@pytest.fixture()
def product():
    return Product.objects.create(
        sku="HIST-001",
        name="History Product",
        price=Decimal("10.00"),
        stock_quantity=5,
        status=ProductStatus.ACTIVE,
    )


def test_service_create_order_generates_initial_history(service, customer, product):
    dto = CreateOrderDTO(
        customer_id=customer.id,
        items=[CreateOrderItemDTO(product_id=product.id, quantity=1)],
    )
    order = service.create_order(dto)

    history = OrderStatusHistory.objects.filter(order=order).order_by("created_at")
    assert history.count() == 1
    assert history.first().new_status == OrderStatus.PENDING
    assert history.first().notes == "Order created"


def test_service_update_status_generates_history(service, customer, product):
    dto = CreateOrderDTO(
        customer_id=customer.id,
        items=[CreateOrderItemDTO(product_id=product.id, quantity=1)],
    )
    order = service.create_order(dto)

    service.update_status(order.id, OrderStatus.CONFIRMED, notes="Auto history")

    history = OrderStatusHistory.objects.filter(order=order).order_by("created_at")
    assert history.count() == 2
    last = history.last()
    assert last.old_status == OrderStatus.PENDING
    assert last.new_status == OrderStatus.CONFIRMED
    assert last.notes == "Auto history"


def test_model_create_and_update_generates_history(customer):
    order = Order.objects.create(customer=customer, notes="Direct order")

    history = OrderStatusHistory.objects.filter(order=order).order_by("created_at")
    assert history.count() == 1
    assert history.first().new_status == OrderStatus.PENDING

    order.status = OrderStatus.CONFIRMED
    order.save()

    history = OrderStatusHistory.objects.filter(order=order).order_by("created_at")
    assert history.count() == 2
    assert history.last().new_status == OrderStatus.CONFIRMED
