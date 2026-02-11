"""Customer API views.

Exposes the ``CustomerService`` via HTTP using DRF ViewSets.
Domain exceptions are caught and translated into appropriate
HTTP status codes — the view never swallows generic exceptions.
"""

from __future__ import annotations

from pydantic import ValidationError as PydanticValidationError

from rest_framework import status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response

from modules.customers.dtos import CreateCustomerDTO, UpdateCustomerDTO
from modules.customers.exceptions import CustomerAlreadyExists, CustomerNotFound
from modules.customers.repositories.django_repository import CustomerDjangoRepository
from modules.customers.serializers import CustomerSerializer
from modules.customers.services import CustomerService


class CustomerViewSet(viewsets.ViewSet):
    """ViewSet for Customer CRUD operations.

    Uses ``CustomerService`` with ``CustomerDjangoRepository`` (DIP).
    Does **not** extend ``ModelViewSet`` — all ORM access goes through
    the service/repository layer.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._service = CustomerService(repository=CustomerDjangoRepository())

    # ------------------------------------------------------------------
    # List / Retrieve
    # ------------------------------------------------------------------

    def list(self, request: Request) -> Response:
        """GET /api/v1/customers/"""
        customers = self._service.list_customers()
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(customers, request)
        serializer = CustomerSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def retrieve(self, request: Request, pk: str = None) -> Response:
        """GET /api/v1/customers/{pk}/"""
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

    def update(self, request: Request, pk: str = None) -> Response:
        """PUT/PATCH /api/v1/customers/{pk}/"""
        data = request.data

        dto = UpdateCustomerDTO(
            name=data.get("name"),
            email=data.get("email"),
            phone=data.get("phone"),
            address=data.get("address"),
            is_active=data.get("is_active"),
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

    def partial_update(self, request: Request, pk: str = None) -> Response:
        """PATCH /api/v1/customers/{pk}/"""
        return self.update(request, pk)

    def destroy(self, request: Request, pk: str = None) -> Response:
        """DELETE /api/v1/customers/{pk}/"""
        try:
            self._service.delete_customer(pk)
        except CustomerNotFound:
            return Response(
                {"detail": "Customer not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
