# Plano de 64 Commits - Sistema ERP Gestão de Pedidos

> **Teste Técnico:** Desenvolvedor Backend Pleno ERP v1  
> **Meta:** 1 commit por etapa, mensagens em inglês, modo imperativo

---

## FASE 1: Setup e Infraestrutura (Etapas 1-8)

| Etapa | Commit Message | Tipo | Descrição |
|-------|----------------|------|-----------|
| 1 | `chore: bootstrap django project structure` | chore | Criar estrutura inicial do projeto Django com DRF |
| 2 | `chore: add docker multi-stage build configuration` | chore | Dockerfile com stages: builder, development, production |
| 3 | `chore: add docker-compose with mysql redis and api services` | chore | Docker Compose com MySQL 8.0, Redis 7 e API Django |
| 4 | `chore: add environment configuration with python-decouple` | chore | Variáveis de ambiente com validação e separação por ambiente |
| 5 | `feat: add health check endpoint at /health` | feat | Endpoint de health check verificando MySQL e Redis |
| 6 | `ci: add github actions workflow for tests and lint` | ci | Pipeline CI com lint, testes e build Docker |
| 7 | `feat: add structured json logging with correlation id` | feat | Logs estruturados em JSON com correlation ID |
| 8 | `chore: configure pytest with django and coverage` | chore | Configuração de pytest, fixtures e cobertura mínima 60% |

---

## FASE 2: Modelagem e Domínio (Etapas 9-16)

| Etapa | Commit Message | Tipo | Descrição |
|-------|----------------|------|-----------|
| 9 | `feat: create base model with soft delete functionality` | feat | Modelo base abstrato com soft delete e manager customizado |
| 10 | `feat: implement customer model with validations` | feat | Modelo Customer com validações de CPF/CNPJ e email únicos |
| 11 | `feat: implement product model with stock control` | feat | Modelo Product com SKU único e controle de estoque |
| 12 | `feat: implement order model with status and idempotency` | feat | Modelo Order com status, order_number auto-gerado e idempotency_key |
| 13 | `feat: implement order item model with calculated subtotal` | feat | Modelo OrderItem com cálculo automático de subtotal |
| 14 | `feat: implement order status history model` | feat | Modelo OrderStatusHistory para rastrear mudanças de status |
| 15 | `feat: implement domain events outbox model` | feat | Modelo OutboxEvent para pattern Outbox |
| 16 | `docs: add er diagram and finalize initial migrations` | docs | Diagrama ER e consolidação de migrations |

---

## FASE 3: Clientes e Produtos - API (Etapas 17-24)

| Etapa | Commit Message | Tipo | Descrição |
|-------|----------------|------|-----------|
| 17 | `feat: implement repository pattern interfaces` | feat | Interfaces de repositório com ABC e abstractmethod |
| 18 | `feat: implement customer repository with django orm` | feat | Implementação DjangoCustomerRepository |
| 19 | `feat: create customer dtos and serializers` | feat | DTOs e serializers para Customer |
| 20 | `feat: implement customer service with business rules` | feat | Service layer para Customer com injeção de dependências |
| 21 | `feat: implement customer api endpoints` | feat | Endpoints REST para Customer com paginação e filtros |
| 22 | `test: add unit and integration tests for customers` | test | Testes unitários e de integração para Customer |
| 23 | `feat: implement product repository and service layer` | feat | Repositório e service para Product |
| 24 | `feat: implement product api endpoints with stock update` | feat | Endpoints REST para Product com atualização de estoque |

---

## FASE 4: Pedidos - Core (Etapas 25-32)

| Etapa | Commit Message | Tipo | Descrição |
|-------|----------------|------|-----------|
| 25 | `feat: define order repository interface` | feat | Interface OrderRepositoryInterface com métodos específicos |
| 26 | `feat: create order dtos for creation and response` | feat | DTOs completos para Order e OrderItem |
| 27 | `feat: implement order serializers with nested items` | feat | Serializers DRF para Order com items aninhados |
| 28 | `feat: implement atomic stock reservation service` | feat | Serviço de reserva atômica com SELECT FOR UPDATE |
| 29 | `feat: implement idempotency service with redis and db fallback` | feat | Serviço de idempotência com Redis e DB fallback |
| 30 | `feat: implement order creation service with all validations` | feat | Service de criação de pedidos com todas as validações |
| 31 | `feat: implement order status state machine` | feat | Máquina de estados para transições de status |
| 32 | `feat: implement order cancellation with stock release` | feat | Cancelamento de pedidos com liberação de estoque |

---

## FASE 5: Pedidos - API e Testes Críticos (Etapas 33-40)

| Etapa | Commit Message | Tipo | Descrição |
|-------|----------------|------|-----------|
| 33 | `feat: implement order repository with django orm` | feat | Implementação do repositório de pedidos |
| 34 | `feat: implement order creation endpoint` | feat | Endpoint POST /api/v1/orders com idempotência |
| 35 | `feat: implement order list and retrieve endpoints` | feat | Endpoints GET para listagem e detalhe de pedidos |
| 36 | `feat: implement order status update and cancel endpoints` | feat | Endpoints PATCH e DELETE para status e cancelamento |
| 37 | `test: add stock concurrency integration test` | test | Teste de integração para concorrência de estoque |
| 38 | `test: add idempotency integration test` | test | Teste de integração para idempotência |
| 39 | `test: add atomicity integration test for partial failures` | test | Teste de integração para atomicidade em falha parcial |
| 40 | `test: add comprehensive unit tests for order service` | test | Testes unitários completos para OrderService |

---

## FASE 6: Eventos e Observabilidade (Etapas 41-48)

| Etapa | Commit Message | Tipo | Descrição |
|-------|----------------|------|-----------|
| 41 | `feat: implement domain events system` | feat | Sistema de eventos de domínio com classes base |
| 42 | `feat: implement outbox pattern for reliable event publishing` | feat | Pattern Outbox para publicação confiável de eventos |
| 43 | `feat: implement event handlers for order events` | feat | Handlers para processar eventos de pedido |
| 44 | `feat: implement automatic status history tracking` | feat | Rastreamento automático de histórico de status |
| 45 | `security: implement rate limiting with redis` | security | Rate limiting usando Redis |
| 46 | `feat: implement correlation id middleware for tracing` | feat | Middleware para correlation ID em todas as requisições |
| 47 | `chore: configure celery with redis broker` | chore | Configuração do Celery com Redis como broker |
| 48 | `test: add e2e tests with playwright` | test | Testes E2E usando Playwright |

---

## FASE 7: Documentação e Qualidade (Etapas 49-56)

| Etapa | Commit Message | Tipo | Descrição |
|-------|----------------|------|-----------|
| 49 | `docs: add openapi schema and swagger ui` | docs | Documentação OpenAPI/Swagger com UI em /docs |
| 50 | `feat: standardize error responses across api` | feat | Padronização de respostas de erro |
| 51 | `chore: configure linting with flake8 black and isort` | chore | Configuração de linting e formatação |
| 52 | `refactor: add type hints to core modules` | refactor | Type hints nos módulos principais |
| 53 | `feat: enhance pagination with cursor-based option` | feat | Melhoria na paginação com opção cursor-based |
| 54 | `feat: enhance filtering and sorting capabilities` | feat | Melhoria em filtros e ordenação |
| 55 | `chore: generate and verify test coverage report` | chore | Relatório de cobertura e verificação mínima |
| 56 | `refactor: code review improvements and optimizations` | refactor | Revisão de código e otimizações |

---

## FASE 8: Documentação Final e Entrega (Etapas 57-64)

| Etapa | Commit Message | Tipo | Descrição |
|-------|----------------|------|-----------|
| 57 | `docs: add comprehensive readme with setup instructions` | docs | README.md completo com instruções |
| 58 | `docs: add architecture documentation` | docs | ARCHITECTURE.md com diagramas e decisões |
| 59 | `docs: add api examples collection` | docs | Coleção de exemplos de API com curl |
| 60 | `chore: add seed data for development` | chore | Dados iniciais para desenvolvimento |
| 61 | `chore: add environment configuration files for dev staging prod` | chore | Arquivos de configuração por ambiente |
| 62 | `test: run final integration test suite` | test | Suite final de testes de integração |
| 63 | `chore: verify docker compose setup end to end` | chore | Verificação completa do Docker Compose |
| 64 | `docs: finalize project for delivery` | docs | Revisão final e preparação para entrega |

---

## Estatísticas de Commits por Tipo

| Tipo | Quantidade | Porcentagem |
|------|------------|-------------|
| feat | 28 | 44% |
| test | 10 | 16% |
| chore | 12 | 19% |
| docs | 8 | 12% |
| refactor | 2 | 3% |
| ci | 1 | 2% |
| security | 1 | 2% |
| **Total** | **64** | **100%** |

---

## Convenção de Mensagens de Commit

### Formato
```
<type>: <description>

[optional body]

[optional footer]
```

### Regras
- Use modo imperativo ("add" não "added")
- Não use ponto final na primeira linha
- Máximo 72 caracteres na primeira linha
- Descrição clara do que o commit faz

### Exemplos
```bash
# Bom
git commit -m "feat: implement atomic stock reservation"
git commit -m "test: add stock concurrency integration test"
git commit -m "docs: add openapi schema and swagger ui"

# Ruim
git commit -m "feat: implemented atomic stock reservation."
git commit -m "adicionando teste"
git commit -m "wip"
```

---

## Checklist de Validação de Commits

- [x] 64 commits criados (um por etapa)
- [x] Mensagens em inglês
- [x] Modo imperativo
- [x] Sem ponto final na primeira linha
- [x] Máximo 72 caracteres na primeira linha
- [x] Tipos de commit corretos
- [x] Histórico mostra evolução do projeto

---

*Plano de commits criado para o Teste Técnico Desenvolvedor Backend Pleno ERP*  
*64 Etapas | Qualidade > Quantidade | Antigravity + Claude Code*
