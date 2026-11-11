"""下单与取消：事务边界、加锁顺序、金额与快照都在这里，视图只做收发。"""

import secrets
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.utils import timezone
from rest_framework import status

from catalog.models import SKU, Product
from common.errors import BusinessError
from promotion.models import UserCoupon

from .models import Order, OrderItem
from .rules import RULES

# MySQL 在唯一冲突的报错里带索引名，用它区分"撞单号"和"同 token 重复提交"。
ORDER_NO_INDEX = "order_no"
CLIENT_TOKEN_INDEX = "uq_order_user_client_token"


def generate_order_no(now=None) -> str:
    """`OD` + 秒级时间 + 6 位随机数：既能人工定位下单时刻，又不暴露单量。"""
    stamp = (now or timezone.now()).strftime("%Y%m%d%H%M%S")
    return f"OD{stamp}{secrets.randbelow(1_000_000):06d}"


def create_order(
    user, items: list[dict], user_coupon_id=None, client_token=None, remark=""
) -> tuple[Order, bool]:
    """创建一个待支付订单，返回 (订单, 是否幂等重放)。

    items 是已通过校验的 `{"sku_id": int, "qty": int}` 列表。
    抛 BusinessError：PRODUCT_OFF_SHELF / STOCK_NOT_ENOUGH / COUPON_NOT_USABLE。
    """
    token = (client_token or "").strip() or None
    if token:
        existing = Order.objects.filter(user=user, client_token=token).first()
        if existing is not None:
            return existing, True

    try:
        with transaction.atomic():
            order = _create_locked(user, items, user_coupon_id, token, remark)
    except IntegrityError as exc:
        # 同 token 并发：赢家已提交，输家必须在事务外回查，否则读不到对方刚写入的行（C5）。
        if token is None or CLIENT_TOKEN_INDEX not in str(exc):
            raise
        existing = Order.objects.filter(user=user, client_token=token).first()
        if existing is None:
            raise
        return existing, True
    return order, False


def cancel_order(user, order_no: str, reason: str = "") -> Order:
    """取消待支付订单；已取消直接返回原单，其他状态抛 ORDER_STATUS_INVALID。"""
    rule = RULES[(Order.Status.PENDING, Order.Status.CANCELLED)]
    with transaction.atomic():
        order = Order.objects.filter(order_no=order_no, user=user).first()
        if order is None:
            # 他人订单同样 404，不能让单号成为探测手段。
            raise BusinessError("NOT_FOUND", "订单不存在", status.HTTP_404_NOT_FOUND)

        if not _apply_transition(order, rule.target, fields={"cancel_reason": reason[:200]}):
            order.refresh_from_db()
            if order.status == rule.target:
                return order
            raise BusinessError("ORDER_STATUS_INVALID", "当前状态不能取消", status.HTTP_409_CONFLICT)
        order.refresh_from_db()
        return order


def close_order(order_no: str, now=None) -> Order | None:
    """关闭已到期未支付订单；返回关掉的订单，未关闭（已支付/已取消/未到期）返回 None。"""
    now = now or timezone.now()
    with transaction.atomic():
        order = Order.objects.filter(order_no=order_no).first()
        if order is None:
            return None
        # 到期判断放进 WHERE：扫表时读到的 expire_at 只是候选条件，不能当关闭依据。
        closed = _apply_transition(
            order,
            Order.Status.CLOSED,
            extra=Q(expire_at__lt=now),
            fields={"closed_at": now},
        )
        if not closed:
            return None
        order.refresh_from_db()
        return order


def close_expired_orders(batch: int = 100, now=None) -> dict[str, int]:
    """扫到期未支付订单并逐单关闭；返回 scanned / closed / skipped 三个计数。"""
    now = now or timezone.now()
    candidates = list(
        Order.objects.filter(status=Order.Status.PENDING, expire_at__lt=now)
        .order_by("expire_at")
        .values_list("order_no", flat=True)[:batch]
    )
    closed = sum(1 for order_no in candidates if close_order(order_no, now=now))
    return {"scanned": len(candidates), "closed": closed, "skipped": len(candidates) - closed}


def _apply_transition(order: Order, target: int, *, extra=None, fields=None) -> bool:
    """条件更新的唯一执行器；返回是否由本次调用完成迁移（赢家）。

    先读状态再 save 的写法在并发下会双回补，见 stocklab/close_lab.py 的反例。
    """
    rule = RULES[(Order.Status.PENDING, target)]
    queryset = Order.objects.filter(pk=order.pk, status=rule.source)
    if extra is not None:
        queryset = queryset.filter(extra)
    moved = queryset.update(status=rule.target, updated_at=timezone.now(), **(fields or {}))
    if not moved:
        return False
    for effect in rule.effects:
        EFFECTS[effect](order)
    return True


def _create_locked(user, items: list[dict], user_coupon_id, token, remark) -> Order:
    now = timezone.now()
    skus = _lock_skus(items)
    _ensure_on_shelf(skus, items)

    total = sum((skus[item["sku_id"]].price * item["qty"] for item in items), Decimal("0.00"))
    user_coupon, discount = _lock_coupon(user, user_coupon_id, total, now)

    if user_coupon is not None:
        redeemed = UserCoupon.objects.filter(pk=user_coupon.pk, status=UserCoupon.Status.UNUSED).update(
            status=UserCoupon.Status.USED, used_at=now
        )
        if not redeemed:
            raise BusinessError("COUPON_NOT_USABLE", "优惠券已被使用", status.HTTP_409_CONFLICT)

    for item in items:
        sku = skus[item["sku_id"]]
        sku.stock -= item["qty"]
        sku.version += 1
        sku.save(update_fields=["stock", "version", "updated_at"])

    order = _insert_order(
        user=user,
        user_coupon=user_coupon,
        total_amount=total,
        discount_amount=discount,
        pay_amount=total - discount,
        expire_at=now + timedelta(minutes=settings.ORDER_EXPIRE_MINUTES),
        client_token=token,
        remark=remark,
    )
    OrderItem.objects.bulk_create(
        [
            OrderItem(
                order=order,
                sku=skus[item["sku_id"]],
                sku_code=skus[item["sku_id"]].sku_code,
                title=skus[item["sku_id"]].title,
                unit_price=skus[item["sku_id"]].price,
                qty=item["qty"],
                subtotal=skus[item["sku_id"]].price * item["qty"],
            )
            for item in items
        ]
    )
    return order


def _lock_skus(items: list[dict]) -> dict[int, SKU]:
    """按 id 升序加锁：多明细下单时加锁顺序一致才不会互相成环。"""
    ids = sorted({item["sku_id"] for item in items})
    locked = SKU.objects.select_for_update().filter(pk__in=ids).order_by("id")
    return {sku.pk: sku for sku in locked}


def _ensure_on_shelf(skus: dict[int, SKU], items: list[dict]) -> None:
    # 商品的上架状态另查一次：select_for_update 带 select_related 会连 product 行一起锁，
    # 而 product 行对本事务没有并发意义。
    active_products = set(
        Product.objects.filter(pk__in={sku.product_id for sku in skus.values()}, is_active=True).values_list(
            "pk", flat=True
        )
    )
    for item in items:
        sku = skus.get(item["sku_id"])
        if sku is None or not sku.is_active or sku.product_id not in active_products:
            raise BusinessError("PRODUCT_OFF_SHELF", "商品不存在或已下架", status.HTTP_409_CONFLICT)
        if sku.stock < item["qty"]:
            raise BusinessError("STOCK_NOT_ENOUGH", f"{sku.title} 库存不足", status.HTTP_409_CONFLICT)


def _lock_coupon(user, user_coupon_id, total: Decimal, now) -> tuple[UserCoupon | None, Decimal]:
    if user_coupon_id is None:
        return None, Decimal("0.00")

    user_coupon = (
        UserCoupon.objects.select_for_update()
        .select_related("coupon")
        .filter(pk=user_coupon_id, user=user)
        .first()
    )
    if user_coupon is None:
        raise BusinessError("COUPON_NOT_USABLE", "优惠券不可用", status.HTTP_409_CONFLICT)

    coupon = user_coupon.coupon
    if (
        user_coupon.status != UserCoupon.Status.UNUSED
        or not coupon.is_active
        or not (coupon.start_at <= now <= coupon.end_at)
    ):
        raise BusinessError("COUPON_NOT_USABLE", "优惠券不可用", status.HTTP_409_CONFLICT)
    if total < coupon.threshold_amount:
        raise BusinessError(
            "COUPON_NOT_USABLE", f"订单满 {coupon.threshold_amount} 才能使用这张券", status.HTTP_409_CONFLICT
        )
    # 券面额大于订单金额时不找零，应付最多减到 0。
    return user_coupon, min(coupon.discount_amount, total)


def _insert_order(**fields) -> Order:
    """撞单号时重生成一次；用保存点包住，否则一次失败就把外层事务打成不可用。"""
    last_error: IntegrityError | None = None
    for _ in range(2):
        try:
            with transaction.atomic():
                return Order.objects.create(order_no=generate_order_no(), **fields)
        except IntegrityError as exc:
            if ORDER_NO_INDEX not in str(exc):
                raise
            last_error = exc
    raise last_error


def _restock(order: Order) -> None:
    quantities: dict[int, int] = {}
    for sku_id, qty in order.items.exclude(sku__isnull=True).values_list("sku_id", "qty"):
        quantities[sku_id] = quantities.get(sku_id, 0) + qty

    now = timezone.now()
    for sku_id in sorted(quantities):
        # F() 单语句自增，避免取消与下单交叉时用陈旧值覆盖库存。
        SKU.objects.filter(pk=sku_id).update(
            stock=F("stock") + quantities[sku_id], version=F("version") + 1, updated_at=now
        )


def _return_coupon(order: Order) -> None:
    if order.user_coupon_id is None:
        return
    UserCoupon.objects.filter(pk=order.user_coupon_id, status=UserCoupon.Status.USED).update(
        status=UserCoupon.Status.UNUSED, used_at=None
    )


EFFECTS = {
    "restock": _restock,
    "return_coupon": _return_coupon,
}
