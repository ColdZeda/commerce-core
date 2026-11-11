"""库存扣减的三种写法：A 悲观锁（与主流程同构）、B 乐观锁（对照）、裸版反例（证明测试不是空转）。"""

import random
import time

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from catalog.models import SKU

B_MAX_RETRIES = 3
OK = "OK"
NOT_ENOUGH = "NOT_ENOUGH"
RETRY_EXHAUSTED = "RETRY_EXHAUSTED"


def deduct_locked(sku_id: int, qty: int) -> str:
    """A：事务内 SELECT ... FOR UPDATE，校验后写回；与 trade.services 的扣减语义一致。"""
    with transaction.atomic():
        sku = SKU.objects.select_for_update().filter(pk=sku_id).first()
        if sku is None or sku.stock < qty:
            return NOT_ENOUGH
        sku.stock -= qty
        sku.version += 1
        sku.save(update_fields=["stock", "version", "updated_at"])
    return OK


def deduct_optimistic(sku_id: int, qty: int, max_retries: int = B_MAX_RETRIES) -> str:
    """B：读版本号 → 带 version 与 stock>=qty 的条件 UPDATE；冲突退避重试，超次数记 RETRY_EXHAUSTED。"""
    for attempt in range(max_retries):
        snapshot = SKU.objects.filter(pk=sku_id).values("version", "stock").first()
        if snapshot is None or snapshot["stock"] < qty:
            return NOT_ENOUGH
        updated = SKU.objects.filter(pk=sku_id, version=snapshot["version"], stock__gte=qty).update(
            stock=F("stock") - qty, version=F("version") + 1, updated_at=timezone.now()
        )
        if updated:
            return OK
        time.sleep(random.uniform(0.001, 0.003) * (attempt + 1))
    return RETRY_EXHAUSTED


def deduct_unprotected(sku_id: int, qty: int, window: float = 0.02, before_write=None) -> str:
    """反例：先读后写、不加锁不加条件。故意留在实验区，用来证明并发断言真能变红。

    before_write 给测试用：让所有线程都读到同一份快照后再写，避免反例因线程启动顺序而偶发。
    """
    sku = SKU.objects.filter(pk=sku_id).first()
    if sku is None or sku.stock < qty:
        return NOT_ENOUGH
    time.sleep(window)
    if before_write is not None:
        before_write()
    sku.stock -= qty
    sku.version += 1
    sku.save(update_fields=["stock", "version", "updated_at"])
    return OK
