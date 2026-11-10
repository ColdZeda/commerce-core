"""就绪探针：db 与 redis 同时可达才算健康，任一失败返回 503。

两个探针都设短超时：探针卡住会把请求压在 uWSGI worker 里，触发 harakiri 连锁。
"""

from __future__ import annotations

import redis
from django.conf import settings
from django.db import connections
from django.http import JsonResponse


def _check_db() -> bool:
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            return cursor.fetchone() == (1,)
    except Exception:
        return False


def _check_redis() -> bool:
    try:
        client = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1)
        return bool(client.ping())
    except Exception:
        return False


def health(request):
    checks = {"db": _check_db(), "redis": _check_redis()}
    healthy = all(checks.values())
    body = {"status": "ok" if healthy else "error", **checks}
    return JsonResponse(body, status=200 if healthy else 503)
