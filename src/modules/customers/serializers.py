"""Customer DRF serializers for API input/output.

The serializer operates at the Interface layer (API Views).
It handles HTTP-level concerns: request parsing, response rendering,
and DRF-native uniqueness validation.  Business logic lives in the
Service Layer, which receives Pydantic DTOs from ``dtos.py``.
"""

from __future__ import annotations

from rest_framework import serializers

from modules.customers.models import Customer


class CustomerSerializer(serializers.ModelSerializer):
    """Read/write serializer for the Customer resource.

    Uses ``ModelSerializer`` to leverage automatic ``UniqueValidator``
    on ``document`` and ``email`` fields (RN-CLI-001, RN-CLI-002).
    """

    class Meta:
        model = Customer
        fields = [
            "id",
            "name",
            "document",
            "document_type",
            "email",
            "phone",
            "address",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
