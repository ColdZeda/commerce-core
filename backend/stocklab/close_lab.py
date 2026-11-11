"""反例：先查状态再回补的关单写法。只出现在实验区，用来证明关单测试会红。"""

from django.db.models import F
from django.utils import timezone

from catalog.models import SKU
from trade.models import Order


def close_unprotected(order_no: str, now=None, before_restock=None) -> bool:
    """先读状态、再回补、最后 save：读取和写入之间没有任何保护。

    before_restock 给测试用：让两个线程都读到 PENDING 之后再各自回补。
    """
    order = Order.objects.filter(order_no=order_no).first()
    if order is None or order.status != Order.Status.PENDING:
        return False
    if before_restock is not None:
        before_restock()
    for sku_id, qty in order.items.exclude(sku__isnull=True).values_list("sku_id", "qty"):
        SKU.objects.filter(pk=sku_id).update(stock=F("stock") + qty)
    order.status = Order.Status.CLOSED
    order.closed_at = now or timezone.now()
    order.save(update_fields=["status", "closed_at"])
    return True
