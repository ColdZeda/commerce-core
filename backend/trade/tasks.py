"""关单任务：只负责批量扫描与计数，状态迁移和副作用都在 services 里。"""

from celery import shared_task

from .services import close_expired_orders as _close_expired_orders


@shared_task
def close_expired_orders(batch: int = 100) -> dict[str, int]:
    """扫描并关闭到期未支付订单；返回 {scanned, closed, skipped}。"""
    return _close_expired_orders(batch=batch)
