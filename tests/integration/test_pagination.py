"""Integration tests for standardized pagination."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from modules.products.models import Product

pytestmark = pytest.mark.integration

User = get_user_model()


@pytest.fixture()
def auth_client():
    """APIClient with a force-authenticated Django user."""
    client = APIClient()
    user = User.objects.create_user(username="pagination_user", password="testpass123")
    client.force_authenticate(user=user)
    return client


@pytest.fixture()
def product_batch():
    """Create a batch of products for pagination tests."""
    products = []
    for idx in range(1, 121):
        products.append(
            Product(
                sku=f"SKU-{idx:03d}",
                name=f"Product {idx:03d}",
                description="Batch product",
                price=Decimal("9.99"),
                stock_quantity=10,
            )
        )
    Product.objects.bulk_create(products)
    return products


class TestPagination:
    def test_default_page_size(self, auth_client, product_batch):
        response = auth_client.get("/api/v1/products/")
        assert response.status_code == 200
        assert len(response.data["results"]) == 20
        assert response.data["next"] is not None
        assert response.data["previous"] is None

    def test_custom_page_size(self, auth_client, product_batch):
        response = auth_client.get("/api/v1/products/?page_size=50")
        assert response.status_code == 200
        assert len(response.data["results"]) == 50
        assert response.data["next"] is not None

    def test_max_page_size(self, auth_client, product_batch):
        response = auth_client.get("/api/v1/products/?page_size=1000")
        assert response.status_code == 200
        assert len(response.data["results"]) == 100
        assert response.data["next"] is not None
