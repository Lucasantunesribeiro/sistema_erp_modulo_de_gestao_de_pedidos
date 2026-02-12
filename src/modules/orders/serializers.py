"""Order DRF serializers for API input/output.

The serializer operates at the Interface layer (API Views).
Business logic lives in the Service Layer, which receives
Pydantic DTOs from ``dtos.py``.
"""

from __future__ import annotations

from rest_framework import serializers

from modules.orders.models import Order, OrderItem, OrderStatusHistory

# ---------------------------------------------------------------------------
# Input Serializers
# ---------------------------------------------------------------------------


class CreateOrderItemSerializer(serializers.Serializer):
    """Validates a single item in an order creation request."""

    product_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)


class CreateOrderSerializer(serializers.Serializer):
    """Validates the order creation request payload."""

    customer_id = serializers.UUIDField()
    items = CreateOrderItemSerializer(many=True, allow_empty=False)
    notes = serializers.CharField(required=False, default="", allow_blank=True)


# ---------------------------------------------------------------------------
# Output Serializers (Read)
# ---------------------------------------------------------------------------


class OrderItemSerializer(serializers.ModelSerializer):
    """Read serializer for order items with product snapshot."""

    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product_id",
            "product_name",
            "product_sku",
            "quantity",
            "unit_price",
            "subtotal",
        ]
        read_only_fields = fields


class StatusHistorySerializer(serializers.ModelSerializer):
    """Read serializer for order status history records."""

    class Meta:
        model = OrderStatusHistory
        fields = [
            "id",
            "old_status",
            "new_status",
            "notes",
            "created_at",
        ]
        read_only_fields = fields


class OrderSerializer(serializers.ModelSerializer):
    """Read serializer for orders with nested items and history."""

    items = OrderItemSerializer(many=True, read_only=True)
    status_history = StatusHistorySerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "customer_id",
            "status",
            "total_amount",
            "notes",
            "created_at",
            "updated_at",
            "items",
            "status_history",
        ]
        read_only_fields = fields


class OrderListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for order list (no nested relations)."""

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "customer_id",
            "status",
            "total_amount",
            "created_at",
        ]
        read_only_fields = fields
