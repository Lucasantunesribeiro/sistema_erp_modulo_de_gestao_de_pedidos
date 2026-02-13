"""Integration tests for filtering, search, ordering, and pagination."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from modules.customers.models import Customer, DocumentType
from modules.orders.models import Order
from modules.products.models import Product

pytestmark = pytest.mark.integration

User = get_user_model()


@pytest.fixture()
def auth_client():
    client = APIClient()
    user = User.objects.create_user(username="filter_user", password="testpass123")
    client.force_authenticate(user=user)
    return client


@pytest.fixture()
def customer_batch():
    customer_active = Customer.objects.create(
        name="Alice Silva",
        document="59860184275",
        document_type=DocumentType.CPF,
        email="alice@example.com",
        is_active=True,
    )
    customer_inactive = Customer.objects.create(
        name="Bob Souza",
        document="11222333000181",
        document_type=DocumentType.CNPJ,
        email="bob@example.com",
        is_active=False,
    )
    return customer_active, customer_inactive


@pytest.fixture()
def product_batch():
    cheap = Product.objects.create(
        sku="SKU-CHEAP",
        name="Cheap Widget",
        description="Budget",
        price=Decimal("9.99"),
        stock_quantity=10,
        status="active",
    )
    premium = Product.objects.create(
        sku="SKU-PREMIUM",
        name="Premium Widget",
        description="Luxury",
        price=Decimal("199.99"),
        stock_quantity=5,
        status="active",
    )
    return cheap, premium


@pytest.fixture()
def order_batch(customer_batch):
    customer_active, _ = customer_batch
    now = timezone.now()
    old_order = Order.objects.create(
        customer=customer_active,
        status="pending",
        total_amount=Decimal("50.00"),
    )
    Order.objects.filter(id=old_order.id).update(created_at=now - timedelta(days=2))
    recent_order = Order.objects.create(
        customer=customer_active,
        status="confirmed",
        total_amount=Decimal("150.00"),
    )
    return old_order, recent_order


class TestCustomerFiltering:
    def test_filter_by_name(self, auth_client, customer_batch):
        response = auth_client.get("/api/v1/customers/?name=Alice")
        assert response.status_code == 200
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["name"] == "Alice Silva"

    def test_search_customer(self, auth_client, customer_batch):
        response = auth_client.get("/api/v1/customers/?search=alice@example.com")
        assert response.status_code == 200
        assert len(response.data["results"]) == 1

    def test_ordering_customers(self, auth_client, customer_batch):
        response = auth_client.get("/api/v1/customers/?ordering=name")
        assert response.status_code == 200
        names = [item["name"] for item in response.data["results"]]
        assert names == sorted(names)


class TestProductFiltering:
    def test_filter_price_range(self, auth_client, product_batch):
        response = auth_client.get("/api/v1/products/?min_price=100&max_price=200")
        assert response.status_code == 200
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["sku"] == "SKU-PREMIUM"

    def test_search_product(self, auth_client, product_batch):
        response = auth_client.get("/api/v1/products/?search=Premium")
        assert response.status_code == 200
        assert len(response.data["results"]) == 1

    def test_ordering_products(self, auth_client, product_batch):
        response = auth_client.get("/api/v1/products/?ordering=price")
        assert response.status_code == 200
        prices = [Decimal(item["price"]) for item in response.data["results"]]
        assert prices == sorted(prices)


class TestOrderFiltering:
    def test_filter_by_status(self, auth_client, order_batch):
        response = auth_client.get("/api/v1/orders/?status=pending")
        assert response.status_code == 200
        assert len(response.data["results"]) == 1

    def test_filter_date_range(self, auth_client, order_batch):
        start_date = (timezone.now() - timedelta(days=1)).date().isoformat()
        response = auth_client.get(f"/api/v1/orders/?start_date={start_date}")
        assert response.status_code == 200
        assert len(response.data["results"]) == 1

    def test_ordering_orders(self, auth_client, order_batch):
        response = auth_client.get("/api/v1/orders/?ordering=total_amount")
        assert response.status_code == 200
        totals = [Decimal(item["total_amount"]) for item in response.data["results"]]
        assert totals == sorted(totals)


class TestCombinedQuery:
    def test_combined_filters_pagination(self, auth_client, product_batch):
        response = auth_client.get(
            "/api/v1/products/?search=widget&ordering=price&page_size=1"
        )
        assert response.status_code == 200
        assert len(response.data["results"]) == 1
        assert response.data["next"] is not None
