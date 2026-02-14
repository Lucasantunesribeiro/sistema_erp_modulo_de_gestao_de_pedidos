"""Product API views.

Exposes the ``ProductService`` via HTTP using DRF ViewSets.
Domain exceptions are caught and translated into appropriate
HTTP status codes — the view never swallows generic exceptions.
"""

from __future__ import annotations

from django_filters.rest_framework import DjangoFilterBackend
from pydantic import ValidationError as PydanticValidationError
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.mixins import ListModelMixin
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from modules.products.dtos import CreateProductDTO, UpdateProductDTO
from modules.products.exceptions import ProductAlreadyExists, ProductNotFound
from modules.products.filters import ProductFilter
from modules.products.models import Product
from modules.products.repositories.django_repository import ProductDjangoRepository
from modules.products.serializers import ProductSerializer
from modules.products.services import ProductService


class ProductViewSet(ListModelMixin, GenericViewSet):
    """ViewSet for Product CRUD operations.

    Uses ``ProductService`` with ``ProductDjangoRepository`` (DIP).
    Does **not** extend ``ModelViewSet`` — all ORM access goes through
    the service/repository layer.
    """

    filterset_class = ProductFilter
    search_fields = ["name", "sku", "description"]
    ordering_fields = ["name", "price", "stock_quantity"]
    ordering = ["-created_at", "-id"]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    queryset = Product.objects.all()
    serializer_class = ProductSerializer

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._service = ProductService(repository=ProductDjangoRepository())

    # ------------------------------------------------------------------
    # List / Retrieve
    # ------------------------------------------------------------------

    def get_queryset(self):
        return self._service.list_products()

    def retrieve(self, request: Request, pk: str | None = None) -> Response:
        """GET /api/v1/products/{pk}/"""
        if pk is None:
            return Response(
                {"detail": "Product not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            product = self._service.get_product(pk)
        except ProductNotFound:
            return Response(
                {"detail": "Product not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = ProductSerializer(product)
        return Response(serializer.data)

    # ------------------------------------------------------------------
    # Create / Update / Destroy
    # ------------------------------------------------------------------

    def create(self, request: Request) -> Response:
        """POST /api/v1/products/"""
        data = request.data

        try:
            dto = CreateProductDTO(
                sku=data.get("sku", ""),
                name=data.get("name", ""),
                price=data.get("price", 0),
                description=data.get("description", ""),
                stock_quantity=data.get("stock_quantity", 0),
            )
        except (PydanticValidationError, ValueError) as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            product = self._service.create_product(dto)
        except ProductAlreadyExists as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_409_CONFLICT,
            )

        out = ProductSerializer(product)
        return Response(out.data, status=status.HTTP_201_CREATED)

    def update(self, request: Request, pk: str | None = None) -> Response:
        """PUT/PATCH /api/v1/products/{pk}/"""
        data = request.data

        try:
            dto = UpdateProductDTO(
                name=data.get("name"),
                price=data.get("price"),
                description=data.get("description"),
                stock_quantity=data.get("stock_quantity"),
                status=data.get("status"),
            )
        except (PydanticValidationError, ValueError) as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if pk is None:
            return Response(
                {"detail": "Product not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            product = self._service.update_product(pk, dto)
        except ProductNotFound:
            return Response(
                {"detail": "Product not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except ProductAlreadyExists as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_409_CONFLICT,
            )

        out = ProductSerializer(product)
        return Response(out.data)

    def partial_update(self, request: Request, pk: str | None = None) -> Response:
        """PATCH /api/v1/products/{pk}/"""
        return self.update(request, pk)

    @action(detail=True, methods=["patch"], url_path="stock")
    def update_stock(self, request: Request, pk: str | None = None) -> Response:
        """PATCH /api/v1/products/{pk}/stock/

        Accepts ``{"stock_quantity": N}`` or ``{"quantity": N}``.
        """
        value = request.data.get("stock_quantity") or request.data.get("quantity")
        if value is None:
            return Response(
                {"detail": "Field 'stock_quantity' or 'quantity' is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            dto = UpdateProductDTO(stock_quantity=int(value))
        except (PydanticValidationError, ValueError) as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if pk is None:
            return Response(
                {"detail": "Product not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            product = self._service.update_product(pk, dto)
        except ProductNotFound:
            return Response(
                {"detail": "Product not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        out = ProductSerializer(product)
        return Response(out.data)

    def destroy(self, request: Request, pk: str | None = None) -> Response:
        """DELETE /api/v1/products/{pk}/"""
        if pk is None:
            return Response(
                {"detail": "Product not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            self._service.delete_product(pk)
        except ProductNotFound:
            return Response(
                {"detail": "Product not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
