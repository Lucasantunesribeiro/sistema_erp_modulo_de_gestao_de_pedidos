# CorpSystem ERP – Architecture

## 1. Overview
**Problem Domain:** Corporate ERP order management with strong consistency and traceability.

**Quality Attributes:**
- **Consistency:** ACID transactions for stock and order state.
- **Traceability:** Status history + structured logs with correlation IDs.
- **Extensibility:** Modular Monolith boundaries + Service Layer.
- **Performance:** Optimized queries and bounded N+1.

## 2. Architectural Patterns Adopted
- **Modular Monolith:** Clear module boundaries inside a single deployable unit.
- **DDD + Clean Architecture:** Domain rules isolated in services and entities.
- **Repository Pattern:** Services depend on interfaces, not ORM.
- **Service Layer:** Business logic centralized, views only handle HTTP.
- **DTOs (Pydantic):** Typed contracts between API and services.
- **Outbox Pattern:** Reliable event publishing.
- **Idempotency (Redis):** Prevents duplicate order creation.

## 3. Data Flow
### 3.1 Order Creation (sync critical path)
1. API validates payload and builds DTO.
2. Service checks customer and product status.
3. Service locks stock (`SELECT FOR UPDATE`).
4. Order + items persisted atomically.
5. Status history recorded + domain events queued.

### 3.2 Order Listing
1. API applies filters/pagination.
2. Repository returns optimized queryset.
3. Serializer returns lightweight payload.

### 3.3 Order Cancellation
1. Service locks order and items.
2. Stock is released atomically.
3. Status history recorded.

## 4. Technical Decisions & Trade-offs
- **MySQL 8.0:** Required by the test; ACID support. Trade-off: fewer advanced features vs PostgreSQL.
- **Redis for cache/idempotency:** High-performance atomic ops. Trade-off: extra infra component.
- **Celery for async:** Mature async processing. Trade-off: extra operational complexity.
- **JWT auth (SimpleJWT):** Standard stateless auth. Trade-off: token management on clients.

## 5. Development Guide
- **Service vs Model vs View:**
  - Service: orchestration + business rules.
  - Model: validation and invariants.
  - View: HTTP and serialization only.

## 6. Folder Map
- `src/config/`: Django settings, URLs, Celery app.
- `src/modules/core/`: base models, middleware, pagination.
- `src/modules/customers/`: Customer domain.
- `src/modules/products/`: Product domain.
- `src/modules/orders/`: Order aggregate.
- `tests/`: Unit + integration tests.
