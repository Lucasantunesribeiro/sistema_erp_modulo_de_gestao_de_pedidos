"""Integration tests for OutboxEvent creation from OrderService."""

from __future__ import annotations

from decimal import Decimal

import pytest

from modules.core.models import EventStatus, OutboxEvent
from modules.customers.models import Customer, DocumentType
from modules.customers.repositories.django_repository import CustomerDjangoRepository
from modules.orders.dtos import CreateOrderDTO, CreateOrderItemDTO
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
        name="Outbox Customer",
        document=VALID_CPF,
        document_type=DocumentType.CPF,
        email="outbox@example.com",
        is_active=True,
    )


@pytest.fixture()
def product():
    return Product.objects.create(
        sku="OUTBOX-1",
        name="Outbox Product",
        price=Decimal("10.00"),
        stock_quantity=5,
        status=ProductStatus.ACTIVE,
    )


def test_create_order_writes_outbox_event(service, customer, product):
    dto = CreateOrderDTO(
        customer_id=customer.id,
        items=[CreateOrderItemDTO(product_id=product.id, quantity=1)],
        notes="Outbox create",
    )
    order = service.create_order(dto)

    events = OutboxEvent.objects.filter(
        event_type="OrderCreated", aggregate_id=str(order.id)
    )
    assert events.count() == 1
    event = events.first()
    assert event.topic == "orders"
    assert event.status == EventStatus.PENDING


def test_cancel_order_writes_outbox_event(service, customer, product):
    dto = CreateOrderDTO(
        customer_id=customer.id,
        items=[CreateOrderItemDTO(product_id=product.id, quantity=1)],
        notes="Outbox cancel",
    )
    order = service.create_order(dto)

    service.cancel_order(order.id)

    events = OutboxEvent.objects.filter(
        event_type="OrderCancelled", aggregate_id=str(order.id)
    )
    assert events.count() == 1
    event = events.first()
    assert event.topic == "orders"
    assert event.status == EventStatus.PENDING
