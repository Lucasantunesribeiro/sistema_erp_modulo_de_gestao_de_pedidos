"""Testes de integração para configuração do Celery."""

import pytest


@pytest.fixture(autouse=True)
def _celery_eager(settings):
    """Executa tasks de forma síncrona no processo de teste."""
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True


class TestCeleryConfig:
    """Verifica que o Celery carrega corretamente via Django."""

    def test_celery_app_is_importable(self):
        from config.celery import app

        assert app.main == "erp"

    def test_celery_app_exported_from_init(self):
        from config import celery_app

        assert celery_app.main == "erp"

    def test_celery_broker_url_configured(self, settings):
        assert settings.CELERY_BROKER_URL is not None
        assert "redis" in settings.CELERY_BROKER_URL

    def test_celery_result_backend_configured(self, settings):
        assert settings.CELERY_RESULT_BACKEND is not None
        assert "redis" in settings.CELERY_RESULT_BACKEND

    def test_celery_serializer_is_json(self, settings):
        assert settings.CELERY_TASK_SERIALIZER == "json"
        assert settings.CELERY_RESULT_SERIALIZER == "json"
        assert settings.CELERY_ACCEPT_CONTENT == ["json"]

    def test_celery_timezone_matches_django(self, settings):
        assert settings.CELERY_TIMEZONE == settings.TIME_ZONE


class TestDebugTask:
    """Verifica execução da task de diagnóstico em modo eager."""

    def test_debug_task_returns_success(self):
        from modules.core.tasks import debug_task

        result = debug_task.delay()

        assert result.successful()
        assert result.result["status"] == "ok"

    def test_debug_task_result_contains_message(self):
        from modules.core.tasks import debug_task

        result = debug_task.delay()

        assert "message" in result.result
        assert "Celery is working" in result.result["message"]

    def test_debug_task_direct_call(self):
        from modules.core.tasks import debug_task

        output = debug_task()

        assert output == {"status": "ok", "message": "Celery is working"}
