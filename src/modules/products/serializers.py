"""Product DRF serializers for API input/output.

The serializer operates at the Interface layer (API Views).
Business logic lives in the Service Layer, which receives
Pydantic DTOs from ``dtos.py``.
"""

from __future__ import annotations

from rest_framework import serializers

from modules.products.models import Product


class ProductSerializer(serializers.ModelSerializer):
    """Read/write serializer for the Product resource."""

    class Meta:
        model = Product
        fields = [
            "id",
            "sku",
            "name",
            "description",
            "price",
            "stock_quantity",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
