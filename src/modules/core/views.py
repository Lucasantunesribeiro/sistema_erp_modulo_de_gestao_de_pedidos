import time

from django.core.cache import cache
from django.db import connections
from django.http import JsonResponse
from django.utils import timezone


def health_check(request):
    services = {}
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

    status_code = 200 if overall_healthy else 503

    return JsonResponse(
        {
            "status": "healthy" if overall_healthy else "unhealthy",
            "timestamp": timezone.now().isoformat(),
            "services": services,
        },
        status=status_code,
    )
