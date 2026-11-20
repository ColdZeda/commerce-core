"""购物车写操作：并发只在"第一次加同一 SKU"时出现，靠唯一索引兜底后重试一次。"""

from django.db import IntegrityError, transaction
from rest_framework import status

from catalog.models import SKU
from common.errors import BusinessError

from .models import CartItem

MAX_QTY = 999


def _ensure_sellable(sku: SKU) -> None:
    if not sku.is_active or not sku.product.is_active:
        raise BusinessError("PRODUCT_OFF_SHELF", "商品已下架", status.HTTP_409_CONFLICT)


def _ensure_within_stock(qty: int, sku: SKU) -> None:
    if qty > min(sku.stock, MAX_QTY):
        raise BusinessError("STOCK_NOT_ENOUGH", f"库存只有 {sku.stock} 件", status.HTTP_409_CONFLICT)


def add_item(user, sku: SKU, qty: int) -> CartItem:
    """加购，同 SKU 累加；抛 BusinessError：PRODUCT_OFF_SHELF / STOCK_NOT_ENOUGH。"""
    _ensure_sellable(sku)
    try:
        with transaction.atomic():
            item = CartItem.objects.select_for_update().filter(user=user, sku=sku).first()
            if item is None:
                item = CartItem.objects.create(user=user, sku=sku, qty=qty)
            else:
                # 行已锁住，直接累加即可；先算完再校验，超库存时整个 atomic 回滚。
                item.qty += qty
                item.save(update_fields=["qty", "updated_at"])
            _ensure_within_stock(item.qty, sku)
            return item
    except IntegrityError:
        # 并发首次加购被唯一索引挡下：重来一次就走到"累加"分支。
        with transaction.atomic():
            item = CartItem.objects.select_for_update().get(user=user, sku=sku)
            item.qty += qty
            item.save(update_fields=["qty", "updated_at"])
            _ensure_within_stock(item.qty, sku)
            return item


def update_item(user, item_id: int, qty: int | None = None, selected: bool | None = None) -> CartItem:
    """改数量或勾选；抛 BusinessError：NOT_FOUND / PRODUCT_OFF_SHELF / STOCK_NOT_ENOUGH。"""
    item = CartItem.objects.select_related("sku__product").filter(pk=item_id, user=user).first()
    if item is None:
        raise BusinessError("NOT_FOUND", "购物车里没有这一项", status.HTTP_404_NOT_FOUND)

    fields = []
    if qty is not None:
        _ensure_sellable(item.sku)
        _ensure_within_stock(qty, item.sku)
        item.qty = qty
        fields.append("qty")
    if selected is not None:
        item.selected = selected
        fields.append("selected")

    item.save(update_fields=[*fields, "updated_at"])
    return item


def set_all_selected(user, selected: bool) -> int:
    return CartItem.objects.filter(user=user).update(selected=selected)


def remove_item(user, item_id: int) -> None:
    deleted, _ = CartItem.objects.filter(pk=item_id, user=user).delete()
    if not deleted:
        raise BusinessError("NOT_FOUND", "购物车里没有这一项", status.HTTP_404_NOT_FOUND)


def cart_to_order_items(user, max_lines: int) -> list[dict]:
    """只把勾中的行转成下单入参；一条没勾就报空车，而不是下一张空单。"""
    rows = CartItem.objects.filter(user=user, selected=True).order_by("id")
    if not rows:
        raise BusinessError("CART_EMPTY", "购物车里没有勾选的商品", status.HTTP_409_CONFLICT)
    if rows.count() > max_lines:
        raise BusinessError("CART_TOO_MANY_LINES", f"一单最多 {max_lines} 个 SKU", status.HTTP_409_CONFLICT)
    return [{"sku_id": row.sku_id, "qty": row.qty} for row in rows]


def clear_ordered_items(user) -> int:
    """下单成功后只清掉已下单的（勾中的）行，没勾的留着。"""
    deleted, _ = CartItem.objects.filter(user=user, selected=True).delete()
    return deleted
