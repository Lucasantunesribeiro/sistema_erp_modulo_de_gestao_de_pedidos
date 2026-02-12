"""Tasks assíncronas do módulo core."""

import structlog
from celery import shared_task

logger = structlog.get_logger(__name__)


@shared_task(name="core.debug_task")
def debug_task():
    """Task de diagnóstico para validar que o Celery está operacional."""
    logger.info("debug_task.executed", status="ok")
    return {"status": "ok", "message": "Celery is working"}
