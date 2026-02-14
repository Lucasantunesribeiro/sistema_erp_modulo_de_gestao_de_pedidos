@echo off
setlocal enabledelayedexpansion

cd /d %~dp0\..

echo ==> Running linting
call docker compose run --rm api flake8 src tests || exit /b 1
call docker compose run --rm api black --check src tests || exit /b 1
call docker compose run --rm api isort --check-only src tests || exit /b 1
call docker compose run --rm api mypy --explicit-package-bases --config-file pyproject.toml src tests || exit /b 1

echo ==> Running tests with coverage
call docker compose run --rm api pytest --cov=src --cov-report=term-missing --cov-fail-under=97 || exit /b 1

echo ==> Running security checks (optional)
call docker compose run --rm api bandit --version >nul 2>&1
if %ERRORLEVEL%==0 (
  call docker compose run --rm api bandit -r src || exit /b 1
) else (
  call docker compose run --rm api safety --version >nul 2>&1
  if %ERRORLEVEL%==0 (
    call docker compose run --rm api safety check || exit /b 1
  ) else (
    echo bandit/safety not installed, skipping security checks
  )
)

echo All checks passed.
