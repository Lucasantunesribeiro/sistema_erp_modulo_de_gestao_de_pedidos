# CorpSystem ERP - Order Management Module

[![CI](https://img.shields.io/github/actions/workflow/status/Lucasantunesribeiro/sistema_erp_modulo_de_gestao_de_pedidos/ci.yml?branch=master)](https://github.com/Lucasantunesribeiro/sistema_erp_modulo_de_gestao_de_pedidos/actions)
[![Coverage](https://img.shields.io/badge/coverage-97.57%25-brightgreen)](docs/PHASE_1_TO_7_AUDIT_REPORT.md)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)
[![Django](https://img.shields.io/badge/django-5.0%2B-0c4b33)](https://www.djangoproject.com/)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

## About the Project
CorpSystem ERP is a **high-performance Order Management module** designed for strong consistency,
traceability, and clean extensibility. The backend follows **Modular Monolith** principles with **DDD
and Clean Architecture**, enabling clear boundaries while keeping transactional integrity.

## Technologies Used
- Python 3.12+
- Django 5.0+
- Django REST Framework
- Celery
- Redis
- MySQL 8.0
- Docker + Docker Compose

## Architectural Decisions
Key decisions are documented in `ARCHITECTURE.md`, including Modular Monolith rules, data flow,
and trade-offs.

## Quick Start (Docker - Development)
**Prerequisites:** Docker 24+ and Docker Compose 2.20+.

Environment files:
- `.env.dev.example` (development)
- `.env.staging.example` (staging)
- `.env.prod.example` (production)

```bash
# 1) Clone
git clone https://github.com/Lucasantunesribeiro/sistema_erp_modulo_de_gestao_de_pedidos.git
cd sistema_erp_modulo_de_gestao_de_pedidos

# 2) Environment
cp .env.dev.example .env

# 3) Start services
docker compose up -d --build

# 4) Migrations
docker compose exec api python src/manage.py migrate

# 5) Create admin user
docker compose exec api python src/manage.py createsuperuser

# 6) Seed data
docker compose exec api python src/manage.py seed_data
```

API Docs:
- Swagger UI: http://localhost:8000/api/docs/
- ReDoc: http://localhost:8000/api/redoc/

Health check:
- http://localhost:8000/health

## Manual Setup (No Docker)
1. Create and activate a virtualenv.
2. Install dependencies.
3. Configure `.env` (see `.env.dev.example`, `.env.staging.example`, `.env.prod.example`).
4. Ensure MySQL 8.0 and Redis 7 are running locally.

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.dev.example .env
# edit .env with your local credentials

python src/manage.py migrate
python src/manage.py createsuperuser
python src/manage.py seed_data
python src/manage.py runserver
```

## Tests & Quality
```bash
# Tests (Docker)
docker compose run --rm api pytest

# Coverage (Docker)
docker compose run --rm api pytest --cov=src --cov-report=term-missing --cov-report=html

# Linting (Docker)
docker compose run --rm api flake8 src tests
docker compose run --rm api mypy --explicit-package-bases --config-file pyproject.toml src tests
```

Coverage baseline (Phase 1–7): **97.57%** (see `docs/PHASE_1_TO_7_AUDIT_REPORT.md`).

## Documentation
- `ARCHITECTURE.md`
- `docs/BUSINESS_RULES.md`
- `docs/API_EXAMPLES.md`

## Project Structure
```
.
├── src/                 # Application source
│   ├── config/          # Django settings, URLs, WSGI
│   └── modules/         # Modular monolith domains
│       ├── core/
│       ├── customers/
│       ├── products/
│       └── orders/
└── tests/               # Unit and integration tests
```

## Contributing
- Open an issue with clear reproduction steps.
- Submit PRs with focused scope and tests.
- Commit style: **Conventional Commits** (imperative, <= 72 chars).

## Release / Deploy Prep
Before pushing to `main`, run the local CI script:

```bash
# Linux/Mac
./scripts/check_quality.sh

# Windows
scripts\check_quality.bat
```

## License
MIT
