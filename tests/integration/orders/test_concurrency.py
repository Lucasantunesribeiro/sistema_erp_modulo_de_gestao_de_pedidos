"""Stock concurrency integration test.

Proves that ``SELECT FOR UPDATE`` in ``OrderService.create_order``
correctly serializes concurrent stock reservations under MySQL.

Scenario:
- Product "Gamer PC" with **stock = 5**.
- 10 threads attempt to buy 1 unit each simultaneously.
- Exactly 5 succeed, 5 raise ``InsufficientStock``.
- Final stock is 0 (never negative).

Uses ``TransactionTestCase`` so each thread can see committed data
and MySQL row-level locking behaves realistically.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal

import django
from django.test import TransactionTestCase

from modules.customers.models import Customer, DocumentType
from modules.customers.repositories.django_repository import CustomerDjangoRepository
from modules.orders.dtos import CreateOrderDTO, CreateOrderItemDTO
from modules.orders.exceptions import InsufficientStock
from modules.orders.repositories.django_repository import OrderDjangoRepository
from modules.orders.services import OrderService
from modules.products.models import Product, ProductStatus
from modules.products.repositories.django_repository import ProductDjangoRepository

logger = logging.getLogger(__name__)

VALID_CPF = "59860184275"
INITIAL_STOCK = 5
NUM_WORKERS = 10


class TestStockConcurrency(TransactionTestCase):
    """Prove atomic stock reservation under concurrent load."""

    def setUp(self):
        self.customer = Customer.objects.create(
            name="Concurrency Customer",
            document=VALID_CPF,
            document_type=DocumentType.CPF,
            email="concurrency@example.com",
            is_active=True,
        )
        self.product = Product.objects.create(
            sku="GAMER-PC",
            name="Gamer PC",
            price=Decimal("2999.99"),
            stock_quantity=INITIAL_STOCK,
            status=ProductStatus.ACTIVE,
        )

    def _create_order_in_thread(self, thread_id: int) -> str:
        """Attempt to create an order. Returns 'success' or 'insufficient'.

        Each thread gets its own DB connection via Django's connection
        handling, ensuring realistic concurrent transactions.
        """
        django.db.connections.close_all()

        service = OrderService(
            order_repository=OrderDjangoRepository(),
            customer_repository=CustomerDjangoRepository(),
            product_repository=ProductDjangoRepository(),
        )
        dto = CreateOrderDTO(
            customer_id=self.customer.id,
            items=[
                CreateOrderItemDTO(
                    product_id=self.product.id,
                    quantity=1,
                ),
            ],
            notes=f"Concurrency thread {thread_id}",
        )
        try:
            service.create_order(dto)
            logger.warning("Thread %d: order created successfully", thread_id)
            return "success"
        except InsufficientStock:
            logger.warning("Thread %d: InsufficientStock (expected)", thread_id)
            return "insufficient"

    def test_concurrent_orders_exhaust_stock(self):
        """10 threads buy 1 unit from stock=5: exactly 5 succeed."""
        results = []

        with ThreadPoolExecutor(max_workers=NUM_WORKERS) as pool:
            futures = {
                pool.submit(self._create_order_in_thread, i): i
                for i in range(NUM_WORKERS)
            }
            for future in as_completed(futures):
                results.append(future.result())

        successes = results.count("success")
        failures = results.count("insufficient")

        # Invariant: exactly INITIAL_STOCK orders succeed
        self.assertEqual(
            successes,
            INITIAL_STOCK,
            f"Expected {INITIAL_STOCK} successes, got {successes}",
        )
        self.assertEqual(
            failures,
            NUM_WORKERS - INITIAL_STOCK,
            f"Expected {NUM_WORKERS - INITIAL_STOCK} failures, got {failures}",
        )

        # Invariant: stock never goes negative
        self.product.refresh_from_db()
        self.assertEqual(
            self.product.stock_quantity,
            0,
            f"Stock should be 0, got {self.product.stock_quantity}",
        )

    def test_stock_never_negative(self):
        """Even under contention, stock_quantity >= 0 always holds."""
        results = []

        with ThreadPoolExecutor(max_workers=NUM_WORKERS) as pool:
            futures = {
                pool.submit(self._create_order_in_thread, i): i
                for i in range(NUM_WORKERS)
            }
            for future in as_completed(futures):
                results.append(future.result())

        self.product.refresh_from_db()
        self.assertGreaterEqual(
            self.product.stock_quantity,
            0,
            "Stock went negative — SELECT FOR UPDATE is broken!",
        )

        # Conservation law: initial = sold + remaining
        sold = results.count("success")
        remaining = self.product.stock_quantity
        self.assertEqual(
            INITIAL_STOCK,
            sold + remaining,
            f"Conservation violated: {INITIAL_STOCK} != {sold} + {remaining}",
        )
