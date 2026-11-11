"""B 的完整下单：单 SKU、无券，只用于和 A 的完整下单同表比较；边界差异必须写进报告。"""

import random
import time
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from catalog.models import SKU
from trade.models import Order, OrderItem
from trade.services import generate_order_no

from .deduct import B_MAX_RETRIES, NOT_ENOUGH, OK, RETRY_EXHAUSTED


def create_order_optimistic(user, sku_id: int, qty: int = 1, max_retries: int = B_MAX_RETRIES):
    """返回 (状态, 订单)，状态取 OK / NOT_ENOUGH / RETRY_EXHAUSTED。"""
    for attempt in range(max_retries):
        with transaction.atomic():
            snapshot = SKU.objects.filter(pk=sku_id).values("version", "stock").first()
            if snapshot is None or snapshot["stock"] < qty:
                return NOT_ENOUGH, None
            updated = SKU.objects.filter(pk=sku_id, version=snapshot["version"], stock__gte=qty).update(
                stock=F("stock") - qty, version=F("version") + 1, updated_at=timezone.now()
            )
            if updated:
                return OK, _write_order(user, sku_id, qty)
        time.sleep(random.uniform(0.001, 0.003) * (attempt + 1))
    return RETRY_EXHAUSTED, None


def _write_order(user, sku_id: int, qty: int) -> Order:
    sku = SKU.objects.get(pk=sku_id)
    total = sku.price * qty
    fields = {
        "user": user,
        "total_amount": total,
        "pay_amount": total,
        "expire_at": timezone.now() + timedelta(minutes=settings.ORDER_EXPIRE_MINUTES),
    }
    order = _insert_with_unique_no(fields)
    OrderItem.objects.create(
        order=order,
        sku=sku,
        sku_code=sku.sku_code,
        title=sku.title,
        unit_price=sku.price,
        qty=qty,
        subtotal=total,
    )
    return order


def _insert_with_unique_no(fields) -> Order:
    # 压测一秒钟能出上百单，单号随机尾数会撞；这里和主流程一样用保存点重生成一次。
    for _ in range(2):
        try:
            with transaction.atomic():
                return Order.objects.create(order_no=generate_order_no(), **fields)
        except IntegrityError:
            continue
    raise RuntimeError("order_no 连续两次冲突")
