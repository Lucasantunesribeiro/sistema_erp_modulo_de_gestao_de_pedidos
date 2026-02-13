"""Testes E2E do fluxo de pedidos usando Playwright."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from validate_docbr import CPF

pytestmark = [pytest.mark.e2e]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_create_and_retrieve_order(api_request_context, auth_token):
    headers = _auth_headers(auth_token)

    cpf = CPF().generate()
    customer_payload = {
        "name": "Cliente E2E",
        "document": cpf,
        "document_type": "CPF",
        "email": f"cliente-{uuid4().hex[:8]}@example.com",
    }
    customer_response = api_request_context.post(
        "/api/v1/customers/",
        data=json.dumps(customer_payload),
        headers={**headers, "Content-Type": "application/json"},
    )
    assert customer_response.status == 201
    customer_id = customer_response.json()["id"]

    product_payload = {
        "sku": f"SKU-{uuid4().hex[:8]}",
        "name": "Produto E2E",
        "price": "29.90",
        "description": "Produto criado via teste E2E",
        "stock_quantity": 20,
    }
    product_response = api_request_context.post(
        "/api/v1/products/",
        data=json.dumps(product_payload),
        headers={**headers, "Content-Type": "application/json"},
    )
    assert product_response.status == 201
    product_id = product_response.json()["id"]

    order_payload = {
        "customer_id": customer_id,
        "items": [{"product_id": product_id, "quantity": 1}],
        "notes": "Pedido E2E",
    }
    order_response = api_request_context.post(
        "/api/v1/orders/",
        data=json.dumps(order_payload),
        headers={**headers, "Content-Type": "application/json"},
    )
    assert order_response.status == 201
    order_data = order_response.json()
    order_id = order_data["id"]

    retrieve_response = api_request_context.get(
        f"/api/v1/orders/{order_id}/", headers=headers
    )
    assert retrieve_response.status == 200
    retrieved = retrieve_response.json()

    assert retrieved["id"] == order_id
    assert retrieved["status"] == order_data["status"]
    assert retrieved["items"][0]["product_id"] == product_id
