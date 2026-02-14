from __future__ import annotations

import random
from datetime import timedelta
from decimal import Decimal
from typing import Iterable

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from modules.customers.models import Customer, DocumentType
from modules.orders.constants import OrderStatus
from modules.orders.models import Order, OrderItem
from modules.products.models import Product, ProductStatus


class Command(BaseCommand):
    help = "Seed database with realistic development data."

    def handle(self, *args, **options):
        random.seed(42)
        self.stdout.write("Seeding development data...")

        users_created = self._seed_users()
        customers = self._seed_customers()
        products = self._seed_products()
        orders_created = self._seed_orders(customers, products)

        self.stdout.write(
            self.style.SUCCESS(
                "Seed completed: "
                f"users={users_created}, "
                f"customers={len(customers)}, "
                f"products={len(products)}, "
                f"orders={orders_created}"
            )
        )

    def _seed_users(self) -> int:
        User = get_user_model()
        created = 0
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser("admin", password="admin123")
            created += 1
        if not User.objects.filter(username="manager").exists():
            User.objects.create_user(
                "manager", password="manager123", is_staff=True
            )
            created += 1
        if not User.objects.filter(username="user").exists():
            User.objects.create_user("user", password="user123")
            created += 1
        return created

    def _seed_customers(self) -> list[Customer]:
        self.stdout.write("Creating customers...")
        customers: list[Customer] = []
        seed_customers = [
            ("Ana Souza", "39053344705", DocumentType.CPF, "ana@example.com"),
            ("Bruno Lima", "11222333000181", DocumentType.CNPJ, "bruno@example.com"),
            ("Carla Mendes", "98765432100", DocumentType.CPF, "carla@example.com"),
            ("Daniel Costa", "12345678901", DocumentType.CPF, "daniel@example.com"),
            ("Eduardo Alves", "98765432000155", DocumentType.CNPJ, "eduardo@example.com"),
            ("Fernanda Rocha", "74125896300", DocumentType.CPF, "fernanda@example.com"),
            ("Gabriel Santos", "36925814700", DocumentType.CPF, "gabriel@example.com"),
            ("Helena Ferreira", "25814736900", DocumentType.CPF, "helena@example.com"),
            ("Igor Ramos", "74185296300", DocumentType.CPF, "igor@example.com"),
            ("Julia Oliveira", "15935745600", DocumentType.CPF, "julia@example.com"),
        ]
        for name, document, doc_type, email in seed_customers:
            customer, _ = Customer.objects.get_or_create(
                document=document,
                defaults={
                    "name": name,
                    "document_type": doc_type,
                    "email": email,
                    "is_active": True,
                },
            )
            customers.append(customer)
        self.stdout.write(self.style.SUCCESS("Creating customers... Done!"))
        return customers

    def _seed_products(self) -> list[Product]:
        self.stdout.write("Creating products...")
        products: list[Product] = []
        catalog = [
            ("ELET-001", "Monitor 27\"", "Eletrônicos", Decimal("1299.90")),
            ("ELET-002", "Teclado Mecânico", "Eletrônicos", Decimal("399.90")),
            ("ELET-003", "Mouse Gamer", "Eletrônicos", Decimal("249.90")),
            ("ELET-004", "Notebook 14\"", "Eletrônicos", Decimal("3999.00")),
            ("ELET-005", "Headset", "Eletrônicos", Decimal("299.90")),
            ("MOV-001", "Mesa Escritório", "Móveis", Decimal("899.00")),
            ("MOV-002", "Cadeira Ergonômica", "Móveis", Decimal("1499.00")),
            ("MOV-003", "Estante", "Móveis", Decimal("699.00")),
            ("MOV-004", "Armário", "Móveis", Decimal("1199.00")),
            ("MOV-005", "Sofá 2 lugares", "Móveis", Decimal("2299.00")),
            ("OFF-001", "Papel A4", "Escritório", Decimal("29.90")),
            ("OFF-002", "Caneta Azul", "Escritório", Decimal("4.90")),
            ("OFF-003", "Caderno", "Escritório", Decimal("19.90")),
            ("OFF-004", "Stapler", "Escritório", Decimal("39.90")),
            ("OFF-005", "Post-it", "Escritório", Decimal("12.90")),
            ("OFF-006", "Agenda", "Escritório", Decimal("49.90")),
            ("OFF-007", "Marcador", "Escritório", Decimal("9.90")),
            ("OFF-008", "Calculadora", "Escritório", Decimal("89.90")),
            ("OFF-009", "Lâmpada LED", "Escritório", Decimal("59.90")),
            ("OFF-010", "Suporte Notebook", "Escritório", Decimal("149.90")),
        ]
        for sku, name, category, price in catalog:
            product, _ = Product.objects.get_or_create(
                sku=sku,
                defaults={
                    "name": name,
                    "description": category,
                    "price": price,
                    "stock_quantity": random.randint(10, 200),
                    "status": ProductStatus.ACTIVE,
                },
            )
            products.append(product)
        self.stdout.write(self.style.SUCCESS("Creating products... Done!"))
        return products

    def _seed_orders(self, customers: Iterable[Customer], products: list[Product]) -> int:
        self.stdout.write("Creating orders...")
        orders_created = 0
        customers_list = list(customers)
        if not customers_list or not products:
            self.stdout.write(self.style.WARNING("Skipping orders (no customers/products)."))
            return 0

        status_weights = [
            (OrderStatus.CONFIRMED, 0.35),
            (OrderStatus.DELIVERED, 0.25),
            (OrderStatus.PENDING, 0.20),
            (OrderStatus.CANCELLED, 0.20),
        ]
        statuses = [s for s, _ in status_weights]
        weights = [w for _, w in status_weights]

        for i in range(50):
            customer = random.choice(customers_list)
            status = random.choices(statuses, weights=weights, k=1)[0]

            order, created = Order.objects.get_or_create(
                customer=customer,
                notes=f"Seed order {i + 1}",
                defaults={"status": status, "total_amount": Decimal("0.00")},
            )
            if not created:
                continue

            created_at = timezone.now() - timedelta(days=random.randint(0, 30))
            Order.objects.filter(id=order.id).update(created_at=created_at)

            item_count = random.randint(1, 5)
            total = Decimal("0.00")
            for product in random.sample(products, k=min(item_count, len(products))):
                quantity = random.randint(1, 3)
                item = OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=quantity,
                    unit_price=product.price,
                )
                total += item.subtotal

            Order.objects.filter(id=order.id).update(total_amount=total)
            orders_created += 1

        self.stdout.write(self.style.SUCCESS("Creating orders... Done!"))
        return orders_created
