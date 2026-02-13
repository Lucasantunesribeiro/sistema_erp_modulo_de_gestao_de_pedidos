import time
from typing import Any, Dict

import structlog
from django.core.cache import cache
from django.db import connections
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

logger = structlog.get_logger()


def health_check(request: HttpRequest) -> JsonResponse:
    services: Dict[str, Dict[str, Any]] = {}
    overall_healthy = True

    # Check database
    try:
        start = time.monotonic()
        conn = connections["default"]
        conn.ensure_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        services["database"] = {
            "status": "up",
            "response_time_ms": round((time.monotonic() - start) * 1000, 2),
        }
    except Exception:
        services["database"] = {"status": "down"}
        overall_healthy = False
        logger.error("health_check_db_failure")

    # Check cache (Redis)
    try:
        start = time.monotonic()
        cache.set("_health_check", "ok", 10)
        result = cache.get("_health_check")
        if result != "ok":
            raise ConnectionError("Cache read failed")
        services["cache"] = {
            "status": "up",
            "response_time_ms": round((time.monotonic() - start) * 1000, 2),
        }
    except Exception:
        services["cache"] = {"status": "down"}
        overall_healthy = False
        logger.error("health_check_cache_failure")

    status_code = 200 if overall_healthy else 503

    logger.info(
        "health_check_completed", status="healthy" if overall_healthy else "unhealthy"
    )

    return JsonResponse(
        {
            "status": "healthy" if overall_healthy else "unhealthy",
            "timestamp": timezone.now().isoformat(),
            "services": services,
        },
        status=status_code,
    )


class ProtectedView(APIView):
    """Minimal endpoint that requires a valid JWT.

    Used to verify that Fail-Closed auth works:
    * No token  -> 401
    * Bad token -> 401
    * Valid JWT -> 200
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: HttpRequest) -> Response:
        return Response(
            {
                "message": "authenticated",
                "user": str(request.user),
            }
        )
