"""Testes de integração para throttling na API de pedidos."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient

from modules.customers.models import Customer, DocumentType
from modules.products.models import Product, ProductStatus

pytestmark = pytest.mark.integration

User = get_user_model()

VALID_CPF = "59860184275"


@pytest.fixture()
def auth_client() -> APIClient:
    client = APIClient()
    user = User.objects.create_user(username="throttleuser", password="testpass123")
    client.force_authenticate(user=user)
    return client


@pytest.fixture()
def customer() -> Customer:
    return Customer.objects.create(
        name="Throttle Customer",
        document=VALID_CPF,
        document_type=DocumentType.CPF,
        email="throttle@example.com",
        is_active=True,
    )


@pytest.fixture()
def product() -> Product:
    return Product.objects.create(
        sku="THROTTLE-001",
        name="Throttle Product",
        price=Decimal("10.00"),
        stock_quantity=10,
        status=ProductStatus.ACTIVE,
    )


def _order_payload(customer: Customer, product: Product) -> dict[str, object]:
    return {
        "customer_id": str(customer.id),
        "items": [{"product_id": str(product.id), "quantity": 1}],
        "notes": "Throttle test",
    }


def test_order_creation_is_throttled(auth_client, customer, product):
    cache.clear()
    payload = _order_payload(customer, product)

    for _ in range(5):
        response = auth_client.post("/api/v1/orders/", payload, format="json")
        assert response.status_code == 201

    response = auth_client.post("/api/v1/orders/", payload, format="json")
    assert response.status_code == 429


def test_order_listing_has_higher_limit(auth_client):
    cache.clear()

    for _ in range(5):
        response = auth_client.get("/api/v1/orders/")
        assert response.status_code == 200
