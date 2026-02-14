# API Examples (curl)

> A compact, copy‑and‑paste collection of tested requests for the main flows.

## 0. Setup
```bash
export API_URL="http://localhost:8000/api/v1"
export TOKEN="<your_jwt_access_token>"
```

---

## A) Authentication

### A1. Obtain Access + Refresh Token
```bash
# POST /auth/token/
curl -X POST "$API_URL/auth/token/" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "your_password"
  }'
```

### A2. Refresh Access Token
```bash
# POST /auth/token/refresh/
curl -X POST "$API_URL/auth/token/refresh/" \
  -H "Content-Type: application/json" \
  -d '{
    "refresh": "<your_refresh_token>"
  }'
```

---

## B) Customers & Products

### B1. Create Customer
```bash
# POST /customers/
curl -X POST "$API_URL/customers/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Maria Souza",
    "document": "59860184275",
    "document_type": "CPF",
    "email": "maria@example.com"
  }'
```

### B2. List Customers
```bash
# GET /customers/
curl -X GET "$API_URL/customers/" \
  -H "Authorization: Bearer $TOKEN"
```

### B3. Create Product (with stock)
```bash
# POST /products/
curl -X POST "$API_URL/products/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "sku": "SKU-NEW",
    "name": "Widget Alpha",
    "price": "29.99",
    "description": "A fine widget",
    "stock_quantity": 100
  }'
```

### B4. Update Product Stock
```bash
# PATCH /products/{id}/
curl -X PATCH "$API_URL/products/<product_id>/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "stock_quantity": 200
  }'
```

---

## C) Order Flow (Happy Path)

### C1. Create Order (Idempotent)
```bash
# POST /orders/
curl -X POST "$API_URL/orders/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000" \
  -d '{
    "customer_id": "<customer_id>",
    "items": [
      {"product_id": "<product_id>", "quantity": 2}
    ],
    "notes": "Order created via API"
  }'
```

### C2. Get Order
```bash
# GET /orders/{id}/
curl -X GET "$API_URL/orders/<order_id>/" \
  -H "Authorization: Bearer $TOKEN"
```

### C3. List Orders (Filter by Status)
```bash
# GET /orders/?status=PENDING
curl -X GET "$API_URL/orders/?status=PENDING" \
  -H "Authorization: Bearer $TOKEN"
```

### C4. Update Status (PENDING -> CONFIRMED)
```bash
# PATCH /orders/{id}/
curl -X PATCH "$API_URL/orders/<order_id>/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "CONFIRMED",
    "notes": "Approved by manager"
  }'
```

### C5. Cancel Order
```bash
# POST /orders/{id}/cancel/
curl -X POST "$API_URL/orders/<order_id>/cancel/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "notes": "Customer requested cancellation"
  }'
```

---

## D) Advanced Filters

### D1. Orders by Date (start_date)
```bash
# GET /orders/?start_date=2024-01-01
curl -X GET "$API_URL/orders/?start_date=2024-01-01" \
  -H "Authorization: Bearer $TOKEN"
```

### D2. Products by Price Range
```bash
# GET /products/?min_price=10&max_price=100
curl -X GET "$API_URL/products/?min_price=10&max_price=100" \
  -H "Authorization: Bearer $TOKEN"
```

### D3. Ordering
```bash
# GET /orders/?ordering=-created_at
curl -X GET "$API_URL/orders/?ordering=-created_at" \
  -H "Authorization: Bearer $TOKEN"
```

---

## E) Error Responses (Examples)

### E1. Validation Error (400)
```bash
# POST /customers/ with invalid payload
curl -X POST "$API_URL/customers/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Incomplete"}'
```

Response example:
```json
{
  "type": "validation_error",
  "errors": [
    {"code": "required", "detail": "This field is required."}
  ]
}
```

### E2. Rate Limit Exceeded (429)
```bash
# Trigger the rate limit by sending many requests quickly
curl -X GET "$API_URL/orders/" -H "Authorization: Bearer $TOKEN"
```

Response example:
```json
{
  "type": "throttled",
  "errors": [
    {"code": "throttled", "detail": "Request was throttled."}
  ]
}
```

### E3. Conflict / Idempotency (409)
```bash
# Create order with insufficient stock (conflict)
curl -X POST "$API_URL/orders/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "<customer_id>",
    "items": [{"product_id": "<product_id>", "quantity": 999}]
  }'
```

Response example:
```json
{
  "type": "conflict",
  "errors": [
    {"code": "insufficient_stock", "detail": "Product SKU: requested 999, available 2."}
  ]
}
```
