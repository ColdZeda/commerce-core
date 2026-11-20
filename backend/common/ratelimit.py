"""固定窗口计数限流：Redis 一次 INCR + EXPIRE，够用且不会把写接口锁死。

窗口从第一次请求开始算，不是对齐到整分钟——对齐窗口在边界上能放过两倍流量。
"""

import logging

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class RateLimitExceeded(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = max(retry_after, 1)
        super().__init__("too many requests")


def client_ip(request) -> str:
    """取 nginx 传进来的真实 IP。

    X-Forwarded-For 可以被客户端伪造，所以只在部署形态确定（本机只有一层 nginx）时信任它；
    调试环境没有这个头，回落到 REMOTE_ADDR。
    """
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        # 链路上第一段是真实客户端；后面的是各级代理。
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or "unknown"


def hit(key: str, limit: int, window: int) -> None:
    """记一次并判限；超限抛 RateLimitExceeded，带上还要等多少秒。

    Redis 不可用时**放行**：登录/注册是演示站唯一的人口，缓存挂掉应该是"能用但不设防"，
    而不是"整站没人能注册"。这条取舍写在 docs/plan-changes.md。
    """
    if not getattr(settings, "RATELIMIT_ENABLED", True):
        return

    cache_key = f"ratelimit:{key}"
    try:
        cache.get_or_set(cache_key, 0, timeout=window)
        current = cache.incr(cache_key)
    except Exception:  # noqa: BLE001  Redis 任何异常都放行，只记一条日志
        logger.warning("限流计数失败，本次放行：%s", cache_key)
        return

    if current > limit:
        raise RateLimitExceeded(retry_after=window)
