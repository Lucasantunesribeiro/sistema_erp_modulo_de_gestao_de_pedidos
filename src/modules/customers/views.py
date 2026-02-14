"""Customer API views.

Exposes the ``CustomerService`` via HTTP using DRF ViewSets.
Domain exceptions are caught and translated into appropriate
HTTP status codes — the view never swallows generic exceptions.
"""

from __future__ import annotations

from django_filters.rest_framework import DjangoFilterBackend
from pydantic import ValidationError as PydanticValidationError
from rest_framework import status
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.mixins import ListModelMixin
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from modules.customers.dtos import CreateCustomerDTO, UpdateCustomerDTO
from modules.customers.exceptions import CustomerAlreadyExists, CustomerNotFound
from modules.customers.filters import CustomerFilter
from modules.customers.models import Customer
from modules.customers.repositories.django_repository import CustomerDjangoRepository
from modules.customers.serializers import CustomerSerializer
from modules.customers.services import CustomerService


class CustomerViewSet(ListModelMixin, GenericViewSet):
    """ViewSet for Customer CRUD operations.

    Uses ``CustomerService`` with ``CustomerDjangoRepository`` (DIP).
    Does **not** extend ``ModelViewSet`` — all ORM access goes through
    the service/repository layer.
    """

    filterset_class = CustomerFilter
    search_fields = ["name", "email", "document"]
    ordering_fields = ["name", "created_at"]
    ordering = ["-created_at", "-id"]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._service = CustomerService(repository=CustomerDjangoRepository())

    # ------------------------------------------------------------------
    # List / Retrieve
    # ------------------------------------------------------------------

    def get_queryset(self):
        return CustomerDjangoRepository().list()

    def retrieve(self, request: Request, pk: str | None = None) -> Response:
        """GET /api/v1/customers/{pk}/"""
        if pk is None:
            return Response(
                {"detail": "Customer not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            customer = self._service.get_customer(pk)
        except CustomerNotFound:
            return Response(
                {"detail": "Customer not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = CustomerSerializer(customer)
        return Response(serializer.data)

    # ------------------------------------------------------------------
    # Create / Update / Destroy
    # ------------------------------------------------------------------

    def create(self, request: Request) -> Response:
        """POST /api/v1/customers/"""
        data = request.data

        try:
            dto = CreateCustomerDTO(
                name=data.get("name", ""),
                document=data.get("document", ""),
                document_type=data.get("document_type", ""),
                email=data.get("email", ""),
                phone=data.get("phone", ""),
                address=data.get("address", ""),
            )
        except (PydanticValidationError, ValueError) as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            customer = self._service.create_customer(dto)
        except CustomerAlreadyExists as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_409_CONFLICT,
            )

        out = CustomerSerializer(customer)
        return Response(out.data, status=status.HTTP_201_CREATED)

    def update(self, request: Request, pk: str | None = None) -> Response:
        """PUT/PATCH /api/v1/customers/{pk}/"""
        data = request.data

        dto = UpdateCustomerDTO(
            name=data.get("name"),
            email=data.get("email"),
            phone=data.get("phone"),
            address=data.get("address"),
            is_active=data.get("is_active"),
        )

        if pk is None:
            return Response(
                {"detail": "Customer not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            customer = self._service.update_customer(pk, dto)
        except CustomerNotFound:
            return Response(
                {"detail": "Customer not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except CustomerAlreadyExists as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_409_CONFLICT,
            )

        out = CustomerSerializer(customer)
        return Response(out.data)

    def partial_update(self, request: Request, pk: str | None = None) -> Response:
        """PATCH /api/v1/customers/{pk}/"""
        return self.update(request, pk)

    def destroy(self, request: Request, pk: str | None = None) -> Response:
        """DELETE /api/v1/customers/{pk}/"""
        if pk is None:
            return Response(
                {"detail": "Customer not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            self._service.delete_customer(pk)
        except CustomerNotFound:
            return Response(
                {"detail": "Customer not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    ordering_fields = ["created_at", "id", "name", "email"]
    ordering = ["-created_at", "-id"]
