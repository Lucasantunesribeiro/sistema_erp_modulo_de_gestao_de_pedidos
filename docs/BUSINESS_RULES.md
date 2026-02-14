# Regras de Negócio Obrigatórias
## Sistema ERP - Módulo de Gestão de Pedidos

> **Documento de Referência:** Teste Técnico Desenvolvedor Backend Pleno ERP v1  
> **Stack:** Python + DRF, MySQL, Redis, Docker  
> **Prioridade:** QUALIDADE > QUANTIDADE

---

## 1. Módulo de Clientes

### 1.1 Campos Obrigatórios
| Campo | Tipo | Restrições |
| -------- | ----------- | ------------------------------- |
| nome | string | Obrigatório, máx 255 caracteres |
| cpf_cnpj | string | Único, validado por formato |
| email | string | Único, formato válido |
| telefone | string | Opcional, formato validado |
| endereço | string/text | Opcional |
| status | enum | `ativo` ou `inativo` |

### 1.2 Regras de Negócio
- **RN-CLI-001:** CPF/CNPJ deve ser único no sistema
- **RN-CLI-002:** Email deve ser único no sistema
- **RN-CLI-003:** Cliente inativo não pode realizar pedidos
- **RN-CLI-004:** Soft delete - usar campo `deleted_at` ao invés de exclusão física
- **RN-CLI-005:** Dados sensíveis (CPF/CNPJ) não devem aparecer em logs

---

## 2. Módulo de Produtos

### 2.1 Campos Obrigatórios
| Campo | Tipo | Restrições |
| --------------------- | ------------- | ------------------------------- |
| sku | string | Único, obrigatório |
| nome | string | Obrigatório, máx 255 caracteres |
| descrição | text | Opcional |
| preço | decimal(10,2) | Obrigatório, > 0 |
| quantidade_em_estoque | integer | Obrigatório, >= 0 |
| status | enum | `ativo` ou `inativo` |

### 2.2 Regras de Negócio
- **RN-PRO-001:** SKU deve ser único no sistema
- **RN-PRO-002:** Produto inativo não pode ser vendido
- **RN-PRO-003:** Preço deve ser maior que zero
- **RN-PRO-004:** Estoque não pode ser negativo
- **RN-PRO-005:** Soft delete - usar campo `deleted_at`

---

## 3. Módulo de Pedidos

### 3.1 Campos Obrigatórios
| Campo | Tipo | Restrições |
| --------------- | ------------- | ----------------------------- |
| numero_pedido | string | Único, auto-gerado |
| cliente_id | FK | Referência a cliente ativo |
| status | enum | Ver fluxo de status abaixo |
| valor_total | decimal(10,2) | Calculado automaticamente |
| observacoes | text | Opcional |
| idempotency_key | string | Único, fornecido pelo cliente |
| created_at | datetime | Auto-gerado |
| deleted_at | datetime | Soft delete |

### 3.2 Status do Pedido e Fluxo Válido

```
PENDENTE → CONFIRMADO → SEPARADO → ENVIADO → ENTREGUE
    ↓           ↓
CANCELADO   CANCELADO
```

#### Transições Válidas:
| Status Atual | Próximos Status Válidos |
| ------------ | ----------------------- |
| PENDENTE | CONFIRMADO, CANCELADO |
| CONFIRMADO | SEPARADO, CANCELADO |
| SEPARADO | ENVIADO |
| ENVIADO | ENTREGUE |
| ENTREGUE | (final) |
| CANCELADO | (final) |

#### Regras de Transição:
- **RN-PED-001:** Transições inválidas devem ser rejeitadas com erro 400
- **RN-PED-002:** Cada mudança de status deve gerar registro no histórico
- **RN-PED-003:** Histórico deve conter: status anterior, novo status, data/hora, usuário responsável, observações

---

## 4. Módulo de Itens do Pedido

### 4.1 Campos Obrigatórios
| Campo | Tipo | Restrições |
| -------------- | ------------- | --------------------------- |
| pedido_id | FK | Referência ao pedido |
| produto_id | FK | Referência a produto ativo |
| quantidade | integer | > 0 |
| preco_unitario | decimal(10,2) | Preço do produto no momento |
| subtotal | decimal(10,2) | quantidade × preco_unitario |

---

## 5. Domain Invariants (Enterprise Hardening)
> **Goal:** Zero invalid states in the database. 100% consistency enforced at the Domain level.

### 5.1 Order Aggregates (`Order`)
- **Invariant 1 (Consistency):** An Order MUST have at least one `OrderItem`.
- **Invariant 2 (Value):** `total_amount` MUST equal the sum of (`unit_price` * `quantity`) for all items.
- **Invariant 3 (Status):** `status` transitions are strictly forward-only (except `CANCELLED`).
    - *Forbidden:* `SHIPPED` -> `PENDING`
    - *Forbidden:* `DELIVERED` -> `SHIPPED`
    - *Forbidden:* `CANCELLED` -> `ANY`
- **Invariant 4 (Immutability):** Once `CONFIRMED`, `items` cannot be modified (add/remove/update).
- **Invariant 5 (stock):** `CONFIRMED` order entails a hard stock reservation (or deduction).

### 5.2 Customer Aggregates (`Customer`)
- **Invariant 1 (Uniqueness):** `email` and `cpf_cnpj` must be unique across the entire system.
- **Invariant 2 (State):** A `Customer` cannot be `soft_deleted` if they have `PENDING` or `PROCESSING` orders.
- **Invariant 3 (Credit):** `credit_limit` cannot be negative.

### 5.3 Product Aggregates (`Product`)
- **Invariant 1 (Price):** `price` must be > 0.
- **Invariant 2 (Stock):** `stock_quantity` cannot be negative (enforced by DB constraint + Application Lock).
- **Invariant 3 (SKU):** `sku` is immutable and unique.

---

## 6. DDD Structure & Boundaries
> **Goal:** Explicit Transactional Boundaries. Cross-aggregate communication via IDs or Domain Events only.

### 6.1 Bound Contexts
- **Sales Context:** `Order`, `OrderItem`, `Cart`
- **Catalog Context:** `Product`, `Category`, `PriceHistory`
- **Inventory Context:** `Stock`, `StockMovement`, `Warehouse`
- **Identity Context:** `User`, `Customer`, `Auth`

### 6.2 Aggregates & Roots
| Aggregate Root | Internal Entities | Value Objects | Transactions |
| :------------- | :------------------------- | :-------------------------------- | :---------------------------------------- |
| **Order** | `OrderItem`, `PaymentInfo` | `Address`, `Money`, `OrderStatus` | Atomic save of Order + Items |
| **Product** | `ProductImage`, `Variant` | `SKU`, `Dimensions`, `Weight` | Atomic update of Product details |
| **Customer** | `AddressBook` | `Email`, `CPF`, `Phone` | Customer profile updates |
| **Stock** | `StockEntry` | `Quantity`, `Location` | STRICT serialization (Optimistic Locking) |

### 6.3 Interaction Rules
1. **Rule:** An Aggregate Root NEVER holds a reference to another Aggregate Root object. Use `ID` only.
    - *Correct:* `order.customer_id = "123"`
    - *Incorrect:* `order.customer = CustomerObj` (Lazy loading risks)
2. **Rule:** Transactions cannot span multiple Aggregates efficiently. Use **Domain Events** (Eventual Consistency) for side effects.
    - *Ex:* Order Created -> publish `OrderCreatedEvent` -> Inventory Listener reserves stock.

---

## 7. Controle de Estoque (REGRAS CRÍTICAS)

### 7.1 Reserva Atômica de Estoque
- **RN-EST-001:** Ao criar pedido, estoque deve ser reservado atomicamente
- **RN-EST-002:** Operação deve ser "tudo ou nada" - se um item falhar, todo o pedido falha
- **RN-EST-003:** Múltiplos pedidos simultâneos NÃO podem reservar o mesmo estoque (proteção contra race condition)
- **RN-EST-004:** Se estoque insuficiente, retornar erro 409 (Conflict)

### 7.2 Devolução de Estoque
- **RN-EST-005:** Ao cancelar pedido, todo o estoque reservado deve ser devolvido
- **RN-EST-006:** Devolução deve ser atômica

### 7.3 Cenário de Concorrência Obrigatório
```
Cenário: Produto X tem 10 unidades em estoque
         Dois pedidos simultâneos tentam comprar 8 unidades cada

Resultado Esperado:
- Apenas UM pedido deve ser aceito
- O outro deve falhar com erro de estoque insuficiente
- Estoque final do produto X: 2 unidades
```

---

## 8. Idempotência (REGRA CRÍTICA)

### 8.1 Requisitos
- **RN-IDP-001:** Criação de pedidos deve ser idempotente via `idempotency_key`
- **RN-IDP-002:** `idempotency_key` é fornecido pelo cliente no header ou body
- **RN-IDP-003:** Se chave já existir, retornar pedido existente (status 200 ou 201)
- **RN-IDP-004:** NÃO retornar 409 para requisições idempotentes repetidas
- **RN-IDP-005:** Chave deve ter TTL (Time To Live) definido

### 8.2 Cenário de Idempotência Obrigatório
```
Cenário: Cliente envia mesma requisição 3 vezes (simula retry após timeout)
         Mesma idempotency_key em todas as requisições

Resultado Esperado:
- Apenas UM pedido criado no banco
- Demais requisições retornam o mesmo pedido
- Status: 200 ou 201 (NÃO 409)
```

### 8.3 Implementação Recomendada
- Usar Redis como cache/guard (SET NX + TTL)
- Usar unique constraint no MySQL como fallback
- TTL sugerido: 24 horas

---

## 9. Validações de Criação de Pedido

### 9.1 Validações Obrigatórias
| Validação | Erro | Código HTTP |
| ------------------------ | ---------------------- | ----------- |
| Cliente deve existir | Cliente não encontrado | 404 |
| Cliente deve estar ativo | Cliente inativo | 400 |
| Produto deve existir | Produto não encontrado | 404 |
| Produto deve estar ativo | Produto inativo | 400 |
| Quantidade > 0 | Quantidade inválida | 400 |
| Estoque suficiente | Estoque insuficiente | 409 |
| Preço atualizado | Preço divergente | 400 |

### 9.2 Atomicidade em Falha Parcial
```
Cenário: Pedido com 3 itens
         Item 1: tem estoque ✓
         Item 2: tem estoque ✓
         Item 3: NÃO tem estoque ✗

Resultado Esperado:
- Pedido falha COMPLETAMENTE
- NENHUM estoque reservado
- Estoque de itens 1 e 2 permanece inalterado
```

---

## 10. Soft Delete

### 10.1 Requisitos
- **RN-SFT-001:** Usar campo `deleted_at` (timestamp nullable) em vez de DELETE físico
- **RN-SFT-002:** Registros com `deleted_at` não NULL devem ser excluídos das queries padrão
- **RN-SFT-003:** Implementar manager/queryset customizado para filtrar automaticamente
- **RN-SFT-004:** Endpoint DELETE deve definir `deleted_at` ao invés de remover registro

---

## 11. Paginação, Filtros e Ordenação

### 11.1 Paginação Obrigatória
- Todos os endpoints GET de listagem devem suportar paginação
- Parâmetros: `page` e `limit` (ou `cursor`)
- Limite máximo sugerido: 100 itens por página
- Default: 20 itens por página

### 11.2 Filtros Obrigatórios
| Endpoint | Filtros Sugeridos |
| ---------- | --------------------------------------------------- |
| /customers | name, email, status, created_at |
| /products | name, sku, status, price_min, price_max |
| /orders | status, customer_id, created_at_from, created_at_to |

### 11.3 Ordenação
- Parâmetro: `sort` e `order` (asc/desc)
- Campos ordenáveis devem ser documentados

---

## 12. Rate Limiting

### 12.1 Requisitos
- **RN-RLM-001:** Implementar rate limiting básico usando Redis
- **RN-RLM-002:** Limite por IP ou por cliente
- **RN-RLM-003:** Retornar 429 (Too Many Requests) quando limite excedido
- **RN-RLM-004:** Incluir headers de rate limit nas respostas

### 12.2 Headers Padrão
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 99
X-RateLimit-Reset: 1640995200
```

---

## 13. Event Sourcing / Domain Events

### 13.1 Requisitos
- **RN-EVT-001:** Implementar publicação de eventos para transições de status
- **RN-EVT-002:** Eventos devem conter: tipo, payload, timestamp, aggregate_id
- **RN-EVT-003:** Opções: Event Sourcing completo OU Domain Events + Outbox

### 13.2 Eventos Obrigatórios
| Evento | Quando |
| ------------------ | ----------------- |
| OrderCreated | Pedido criado |
| OrderStatusChanged | Status alterado |
| OrderCancelled | Pedido cancelado |
| StockReserved | Estoque reservado |
| StockReleased | Estoque liberado |

---

## 14. Logs e Observabilidade

### 14.1 Requisitos
- **RN-LOG-001:** Logs estruturados em JSON
- **RN-LOG-002:** Níveis: INFO, WARN, ERROR
- **RN-LOG-003:** Correlation ID opcional (header X-Request-ID)
- **RN-LOG-004:** NÃO logar dados sensíveis (CPF/CNPJ) - mascarar quando necessário
- **RN-LOG-005:** Implementar **OpenTelemetry** para tracing distribuído
- **RN-LOG-006:** Propagar contexto W3C Trace Context (traceparent) entre serviços

---

## 15. Segurança e Supply Chain (OWASP LLM)

### 15.1 Requisitos Críticos
- **RN-SEC-001:** Validar e sanitizar todos os inputs (prevenção de Injection)
- **RN-SEC-002:** Sanitizar outputs antes de renderizar (prevenção de XSS)
- **RN-SEC-003:** Filtrar PII e segredos antes de enviar a LLMs ou logs
- **RN-SEC-004:** Usar lockfiles (poetry.lock / requirements.txt com hashes) para deps
- **RN-SEC-005:** Implementar rate limiting (veja Seção 12) para evitar DoS

---

## 16. Resumo das Regras Críticas (Checklist de Implementação)

### Regras de Estoque (Mais Críticas)
- [ ] RN-EST-001: Reserva atômica ao criar pedido
- [ ] RN-EST-002: Operação "tudo ou nada"
- [ ] RN-EST-003: Proteção contra race condition
- [ ] RN-EST-004: Erro 409 para estoque insuficiente
- [ ] RN-EST-005: Devolução ao cancelar

### Regras de Idempotência (Mais Críticas)
- [ ] RN-IDP-001: Criação idempotente
- [ ] RN-IDP-002: idempotency_key fornecido pelo cliente
- [ ] RN-IDP-003: Retornar pedido existente em replays
- [ ] RN-IDP-004: NÃO usar 409 para replays
- [ ] RN-IDP-005: TTL definido

### Regras de Status (Mais Críticas)
- [ ] RN-PED-001: Validação de transições
- [ ] RN-PED-002: Histórico em cada mudança
- [ ] RN-PED-003: Dados completos no histórico

### Cenários de Teste Obrigatórios
- [ ] Concorrência de estoque (2 pedidos simultâneos)
- [ ] Idempotência (3 requisições idênticas)
- [ ] Atomicidade em falha parcial (3 itens, 1 sem estoque)

---

## 17. Códigos HTTP Padronizados

| Código | Quando Usar |
| ------------------------- | ---------------------------------------- |
| 200 OK | Sucesso em GET, PUT, PATCH |
| 201 Created | Recurso criado com sucesso |
| 400 Bad Request | Dados inválidos, validação falhou |
| 404 Not Found | Recurso não existe |
| 409 Conflict | Estoque insuficiente, conflito de estado |
| 429 Too Many Requests | Rate limit excedido |
| 500 Internal Server Error | Erro inesperado |

---

*Documento gerado com base no Teste Técnico Desenvolvedor Backend Pleno ERP v1*  
*Prioridade: QUALIDADE > QUANTIDADE*
