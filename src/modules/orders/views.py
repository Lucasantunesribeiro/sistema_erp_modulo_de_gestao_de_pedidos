"""Order API views.

Exposes the ``OrderService`` via HTTP using DRF ViewSets.
Domain exceptions are caught and translated into appropriate
HTTP status codes — the view never swallows generic exceptions.
"""

from __future__ import annotations

from uuid import UUID

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import BaseThrottle
from rest_framework.viewsets import GenericViewSet

from modules.core.pagination import StandardResultsSetPagination
from modules.customers.repositories.django_repository import CustomerDjangoRepository
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
from modules.orders.filters import OrderFilter
from modules.orders.models import Order
from modules.orders.repositories.django_repository import OrderDjangoRepository
from modules.orders.serializers import (
    CreateOrderSerializer,
    OrderListSerializer,
    OrderSerializer,
)
from modules.orders.services import OrderService
from modules.products.repositories.django_repository import ProductDjangoRepository


class OrderViewSet(GenericViewSet):
    queryset = Order.objects.all()
    """ViewSet for Order operations.

    Uses ``OrderService`` with injected repositories (DIP).
    Does **not** extend ``ModelViewSet`` — all ORM access goes through
    the service/repository layer.
    """

    filterset_class = OrderFilter
    search_fields = ["id", "customer__name"]
    ordering_fields = ["created_at", "total_amount", "status"]
    ordering = ["-created_at", "-id"]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._service = OrderService(
            order_repository=OrderDjangoRepository(),
            customer_repository=CustomerDjangoRepository(),
            product_repository=ProductDjangoRepository(),
        )

    def get_throttles(self) -> list[BaseThrottle]:
        """Define escopos de throttling por ação."""
        throttle_scope: str | None
        if self.action == "create":
            throttle_scope = "order_creation"
        elif self.action in {"list", "retrieve"}:
            throttle_scope = "order_listing"
        else:
            throttle_scope = None
        self.throttle_scope = throttle_scope
        return super().get_throttles()

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create(self, request: Request) -> Response:
        """POST /api/v1/orders/

        Supports idempotency via the ``Idempotency-Key`` header.
        Returns 200 if the key was already used, 201 for new orders.
        """
        create_serializer = CreateOrderSerializer(data=request.data)
        create_serializer.is_valid(raise_exception=True)

        data = create_serializer.validated_data
        idempotency_key = request.headers.get("Idempotency-Key")
        dto = CreateOrderDTO(
            customer_id=data["customer_id"],
            items=[
                CreateOrderItemDTO(
                    product_id=item["product_id"],
                    quantity=item["quantity"],
                )
                for item in data["items"]
            ],
            notes=data.get("notes", ""),
            idempotency_key=idempotency_key,
        )

        try:
            order = self._service.create_order(dto)
        except CustomerNotFound:
            return Response(
                {"detail": "Customer not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except InactiveCustomer:
            return Response(
                {"detail": "Customer is inactive."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ProductNotFound as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_404_NOT_FOUND,
            )
        except InactiveProduct as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except InsufficientStock as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_409_CONFLICT,
            )

        out = OrderSerializer(order)
        return Response(out.data, status=status.HTTP_201_CREATED)

    # ------------------------------------------------------------------
    # List / Retrieve
    # ------------------------------------------------------------------

    def get_queryset(self):
        return OrderDjangoRepository().list()

    def list(self, request: Request) -> Response:
        """GET /api/v1/orders/

        Filtering (status, customer, date range, total range) is handled
        by ``OrderFilter`` via ``filter_backends``.  Ordering is handled
        by ``OrderingFilter``.  Results are paginated.
        """
        queryset = self.filter_queryset(self.get_queryset())

        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = OrderListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def retrieve(self, request: Request, pk: str | None = None) -> Response:
        """GET /api/v1/orders/{pk}/"""
        if pk is None:
            return Response(
                {"detail": "Order not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            order = self._service.get_order(pk)
        except OrderNotFound:
            return Response(
                {"detail": "Order not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = OrderSerializer(order)
        return Response(serializer.data)

    # ------------------------------------------------------------------
    # Status Update
    # ------------------------------------------------------------------

    def partial_update(self, request: Request, pk: str | None = None) -> Response:
        """PATCH /api/v1/orders/{pk}/

        Updates order status.  Cancellations are **not** allowed via
        this endpoint — use ``POST /orders/{id}/cancel/`` instead.
        """
        if pk is None:
            return Response(
                {"detail": "Order not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        status_value = request.data.get("status")
        if not status_value:
            return Response(
                {"detail": "Field 'status' is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if status_value.upper() == OrderStatus.CANCELLED:
            return Response(
                {"detail": "Use the /cancel/ endpoint for cancellations."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        notes = request.data.get("notes", "")

        try:
            order = self._service.update_status(
                order_id=UUID(pk),
                new_status=status_value,
                notes=notes,
            )
        except OrderNotFound:
            return Response(
                {"detail": "Order not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except InvalidOrderStatus as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ValueError:
            return Response(
                {"detail": "Invalid order ID format."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = OrderSerializer(order)
        return Response(serializer.data)

    # ------------------------------------------------------------------
    # Cancel (dedicated action)
    # ------------------------------------------------------------------

    @action(detail=True, methods=["post"])
    def cancel(self, request: Request, pk: str | None = None) -> Response:
        """POST /api/v1/orders/{pk}/cancel/

        Cancels an order and releases reserved stock (RN-EST-005/006).
        """
        if pk is None:
            return Response(
                {"detail": "Order not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        notes = request.data.get("notes", "")

        try:
            order = self._service.cancel_order(
                order_id=UUID(pk),
                notes=notes,
            )
        except OrderNotFound:
            return Response(
                {"detail": "Order not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except InvalidOrderStatus as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ValueError:
            return Response(
                {"detail": "Invalid order ID format."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = OrderSerializer(order)
        return Response(serializer.data)
