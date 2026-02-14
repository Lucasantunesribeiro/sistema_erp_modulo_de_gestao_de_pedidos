#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "==> Running linting"
docker compose run --rm api flake8 src tests
docker compose run --rm api black --check src tests
docker compose run --rm api isort --check-only src tests
docker compose run --rm api mypy --explicit-package-bases --config-file pyproject.toml src tests

echo "==> Running tests with coverage"
docker compose run --rm api pytest --cov=src --cov-report=term-missing --cov-fail-under=97

echo "==> Running security checks (optional)"
if docker compose run --rm api bandit --version >/dev/null 2>&1; then
  docker compose run --rm api bandit -r src
elif docker compose run --rm api safety --version >/dev/null 2>&1; then
  docker compose run --rm api safety check
else
  echo "bandit/safety not installed, skipping security checks"
fi

echo "All checks passed."
