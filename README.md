# Sistema ERP - Módulo de Gestão de Pedidos

> API REST robusta para gestão de pedidos com arquitetura limpa, princípios SOLID e práticas de DevOps.

[![CI](https://github.com/Lucasantunesribeiro/sistema_erp_modulo_de_gestao_de_pedidos/actions/workflows/ci.yml/badge.svg)](https://github.com/Lucasantunesribeiro/sistema_erp_modulo_de_gestao_de_pedidos/actions)
[![Coverage](https://img.shields.io/badge/coverage-80%25-brightgreen.svg)](https://github.com/Lucasantunesribeiro/sistema_erp_modulo_de_gestao_de_pedidos)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/django-5.0-green.svg)](https://www.djangoproject.com/)

---

## 📋 Sumário

- [Tecnologias Utilizadas](#-tecnologias-utilizadas)
- [Pré-requisitos](#-pré-requisitos)
- [Como Rodar Localmente](#-como-rodar-localmente)
- [Como Rodar os Testes](#-como-rodar-os-testes)
- [Estrutura de Pastas](#-estrutura-de-pastas)
- [Documentação da API](#-documentação-da-api)
- [Decisões Arquiteturais](#-decisões-arquiteturais)
- [Regras de Negócio](#-regras-de-negócio)

---

## 🚀 Tecnologias Utilizadas

### Backend
- **Python** 3.11+
- **Django** 5.0
- **Django REST Framework** 3.15+

### Banco de Dados
- **MySQL** 8.0 (obrigatório)
- **Redis** 7 (cache e idempotência)

### DevOps
- **Docker** + Docker Compose
- **Multi-stage builds**
- **GitHub Actions** (CI/CD)

### Testes
- **Pytest** com cobertura
- **Testes de integração**
- **Testes de concorrência**

### Observabilidade
- **Logs estruturados** (JSON)
- **Correlation ID**
- **OpenTelemetry**

---

## 📦 Pré-requisitos

- Docker 24.0+
- Docker Compose 2.20+
- Git 2.40+

---

## 🔧 Como Rodar Localmente

### 1. Clone o repositório

```bash
git clone https://github.com/Lucasantunesribeiro/sistema_erp_modulo_de_gestao_de_pedidos.git
cd sistema_erp_modulo_de_gestao_de_pedidos
```

### 2. Configure as variáveis de ambiente

```bash
cp .env.example .env
# Edite o arquivo .env com suas configurações
```

### 3. Inicie os serviços com Docker Compose

```bash
docker-compose up -d
```

### 4. Execute as migrations

```bash
docker-compose exec api python manage.py migrate
```

### 5. Crie dados iniciais (opcional)

```bash
docker-compose exec api python manage.py seed
```

### 6. Verifique o health check

```bash
curl http://localhost:8000/health
```

### 7. Acesse a documentação da API

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## 🧪 Como Rodar os Testes

### Todos os testes

```bash
docker-compose exec api pytest
```

### Com cobertura

```bash
docker-compose exec api pytest --cov
```

### Testes específicos

```bash
# Testes de concorrência
docker-compose exec api pytest tests/integration/test_stock_concurrency.py -v

# Testes de idempotência
docker-compose exec api pytest tests/integration/test_idempotency.py -v

# Testes de atomicidade
docker-compose exec api pytest tests/integration/test_atomicity.py -v
```

---

## 📁 Estrutura de Pastas

```
.
├── src/                          # Código fonte
│   ├── config/                   # Configurações do Django
│   │   ├── settings/             # Settings por ambiente
│   │   ├── celery.py             # Configuração do Celery
│   │   └── urls.py               # Rotas principais
│   ├── core/                     # Funcionalidades transversais
│   │   ├── models.py             # Modelo base com soft delete
│   │   ├── repositories/         # Interfaces de repositório
│   │   ├── exceptions/           # Exceções customizadas
│   │   ├── middleware/           # Middlewares (correlation ID)
│   │   └── events/               # Sistema de eventos
│   ├── customers/                # Módulo de clientes
│   │   ├── models.py
│   │   ├── repositories.py
│   │   ├── services.py
│   │   ├── views.py
│   │   └── serializers.py
│   ├── products/                 # Módulo de produtos
│   │   ├── models.py
│   │   ├── repositories.py
│   │   ├── services.py
│   │   ├── views.py
│   │   └── serializers.py
│   ├── orders/                   # Módulo de pedidos
│   │   ├── models.py
│   │   ├── repositories/
│   │   ├── services/
│   │   │   ├── stock_service.py
│   │   │   ├── idempotency_service.py
│   │   │   └── order_service.py
│   │   ├── domain/
│   │   │   └── status_machine.py
│   │   ├── views.py
│   │   └── serializers.py
│   └── manage.py
├── tests/                        # Testes
│   ├── unit/                     # Testes unitários
│   ├── integration/              # Testes de integração
│   ├── e2e/                      # Testes E2E
│   └── conftest.py               # Fixtures globais
├── docs/                         # Documentação
│   ├── api-examples.md           # Exemplos de API
│   └── er-diagram.md             # Diagrama ER
├── .github/
│   └── workflows/
│       └── ci.yml                # Pipeline CI/CD
├── docker-compose.yml            # Docker Compose
├── Dockerfile                    # Dockerfile multi-stage
├── .env.example                  # Exemplo de variáveis de ambiente
├── requirements.txt              # Dependências
├── README.md                     # Este arquivo
└── ARCHITECTURE.md               # Documentação de arquitetura
```

---

## 📚 Documentação da API

### Endpoints Disponíveis

#### Clientes
| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | /api/v1/customers | Criar cliente |
| GET | /api/v1/customers | Listar clientes |
| GET | /api/v1/customers/:id | Obter cliente |
| PATCH | /api/v1/customers/:id | Atualizar cliente |
| DELETE | /api/v1/customers/:id | Remover cliente (soft delete) |

#### Produtos
| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | /api/v1/products | Criar produto |
| GET | /api/v1/products | Listar produtos |
| GET | /api/v1/products/:id | Obter produto |
| PATCH | /api/v1/products/:id | Atualizar produto |
| PATCH | /api/v1/products/:id/stock | Atualizar estoque |
| DELETE | /api/v1/products/:id | Remover produto (soft delete) |

#### Pedidos
| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | /api/v1/orders | Criar pedido |
| GET | /api/v1/orders | Listar pedidos |
| GET | /api/v1/orders/:id | Obter pedido |
| PATCH | /api/v1/orders/:id/status | Atualizar status |
| DELETE | /api/v1/orders/:id | Cancelar pedido |

### Exemplos de Uso

#### Criar um cliente

```bash
curl -X POST http://localhost:8000/api/v1/customers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "João Silva",
    "cpf_cnpj": "123.456.789-00",
    "email": "joao@example.com",
    "phone": "(11) 99999-9999",
    "address": "Rua Exemplo, 123"
  }'
```

#### Criar um produto

```bash
curl -X POST http://localhost:8000/api/v1/products \
  -H "Content-Type: application/json" \
  -d '{
    "sku": "PROD-001",
    "name": "Produto Exemplo",
    "description": "Descrição do produto",
    "price": 99.99,
    "stock_quantity": 100
  }'
```

#### Criar um pedido

```bash
curl -X POST http://localhost:8000/api/v1/orders \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000" \
  -d '{
    "customer_id": 1,
    "items": [
      {"product_id": 1, "quantity": 2},
      {"product_id": 2, "quantity": 1}
    ],
    "notes": "Entregar após as 18h"
  }'
```

#### Atualizar status do pedido

```bash
curl -X PATCH http://localhost:8000/api/v1/orders/1/status \
  -H "Content-Type: application/json" \
  -d '{
    "status": "CONFIRMADO",
    "notes": "Pagamento confirmado"
  }'
```

---

## 🏗️ Decisões Arquiteturais

### Arquitetura: Modular Monolith

Optamos por uma arquitetura de **Monolito Modular** pelos seguintes motivos:

1. **Integridade Transacional**: Operações de pedido e estoque exigem consistência forte (ACID)
2. **Simplicidade Operacional**: Um único container é mais fácil de monitorar e fazer rollback
3. **Velocidade de Desenvolvimento**: Refatorações são mais simples sem contratos entre serviços
4. **Performance**: Chamadas in-process são mais rápidas que HTTP/gRPC

### Padrões Adotados

- **Repository Pattern**: Abstração do acesso a dados
- **Service Layer**: Lógica de negócio isolada
- **DTOs**: Separação entre modelos de domínio e contratos de API
- **Domain Events**: Comunicação entre módulos via eventos
- **Outbox Pattern**: Garantia de entrega de eventos

### Controle de Concorrência

- **Lock Pessimista**: `SELECT ... FOR UPDATE` para reserva de estoque
- **Transações Atômicas**: Garantia de "tudo ou nada"
- **Idempotência**: Chaves únicas com TTL no Redis

Para mais detalhes, consulte o [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 📜 Regras de Negócio

### Estoque
- Reserva atômica ao criar pedido
- Operação "tudo ou nada"
- Proteção contra race condition
- Devolução ao cancelar

### Idempotência
- Criação de pedidos via `idempotency_key`
- Retorna pedido existente em replays
- TTL de 24 horas

### Status do Pedido
```
PENDENTE → CONFIRMADO → SEPARADO → ENVIADO → ENTREGUE
    ↓           ↓
CANCELADO   CANCELADO
```

Para mais detalhes, consulte o [BUSINESS_RULES.md](BUSINESS_RULES.md).

---

## 📄 Licença

Este projeto foi desenvolvido para fins de avaliação técnica.

---

## 👨‍💻 Autor

**Lucas Antunes Ribeiro**

- GitHub: [@Lucasantunesribeiro](https://github.com/Lucasantunesribeiro)

---

*Projeto desenvolvido para o Teste Técnico Desenvolvedor Backend Pleno ERP*
