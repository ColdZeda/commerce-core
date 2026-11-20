"""对账看板：把"库存守恒"算成一张能一眼看懂的账。

口径（按 SKU）：
    账面      = sku.stock（当前列）
    已售      = 待支付 + 已支付订单里该 SKU 的明细数量
    回补      = 已取消 + 已关闭订单里该 SKU 的明细数量
    明细合计  = 全部订单明细数量
    初始      = sku.initial_stock（建档时的基线）
    应有账面  = 初始 - 已售

    为什么减的是"已售"而不是"明细合计"：已售只算还在占用库存的订单（待支付/已支付），
    取消和关闭的明细已经通过 restock 还回去了，重复扣会把账算错。
    回补单独列出来是给人看"退了多少"，不参与这条等式。

会计恒等式有两条：`应有账面 == 账面`、`已售 + 回补 == 明细合计`。
两条都成立才算"平"。没有基线（initial_stock）的账永远平不了，所以基线是建表时记下的。
"""

from django.db.models import Count, Q, Sum
from django.utils import timezone

from catalog.models import SKU
from promotion.models import Coupon, UserCoupon
from trade.models import Order, OrderItem

PENDING_PAID = [Order.Status.PENDING, Order.Status.PAID]
RETURNED = [Order.Status.CANCELLED, Order.Status.CLOSED]


def _sku_rows() -> list[dict]:
    stats = {
        row["sku_id"]: row
        for row in OrderItem.objects.filter(sku__isnull=False)
        .values("sku_id")
        .annotate(
            sold=Sum("qty", filter=Q(order__status__in=PENDING_PAID)),
            restocked=Sum("qty", filter=Q(order__status__in=RETURNED)),
            items_total=Sum("qty"),
        )
    }

    rows = []
    for sku in SKU.objects.select_related("product").all():
        stat = stats.get(sku.pk, {})
        sold = stat.get("sold") or 0
        restocked = stat.get("restocked") or 0
        items_total = stat.get("items_total") or 0
        expected = sku.initial_stock - sold
        rows.append(
            {
                "sku_code": sku.sku_code,
                "product": sku.product.name,
                "title": sku.title,
                "initial": sku.initial_stock,
                "sold": sold,
                "restocked": restocked,
                "stock": sku.stock,
                "items_total": items_total,
                # 两个恒等式合起来判：账面对得上、明细也对得上，才算真的平。
                "balanced": expected == sku.stock and sold + restocked == items_total,
                "diff": sku.stock - expected,
            }
        )
    return rows


def _coupon_rows() -> list[dict]:
    used = {
        row["coupon_id"]: row["used"]
        for row in UserCoupon.objects.values("coupon_id").annotate(
            used=Count("id", filter=Q(status=UserCoupon.Status.USED))
        )
    }
    return [
        {
            "name": coupon.name,
            "issued": coupon.issued_qty,
            "total": coupon.total_qty,
            "used": used.get(coupon.pk, 0),
        }
        for coupon in Coupon.objects.all().order_by("id")
    ]


def _order_counts() -> dict:
    labels = {
        Order.Status.PENDING: "pending",
        Order.Status.PAID: "paid",
        Order.Status.CANCELLED: "cancelled",
        Order.Status.CLOSED: "closed",
    }
    counts = {"pending": 0, "paid": 0, "cancelled": 0, "closed": 0}
    for row in Order.objects.values("status").annotate(count=Count("id")):
        counts[labels[int(row["status"])]] = row["count"]
    counts["total"] = sum(counts.values())
    return counts


def build_report() -> dict:
    rows = _sku_rows()
    unbalanced = [row for row in rows if not row["balanced"]]
    return {
        "generated_at": timezone.now().isoformat(),
        "summary": {
            "skus": len(rows),
            "unbalanced": len(unbalanced),
            "balanced": not unbalanced,
            # 所有 SKU 的账面数量合计，和"已售 - 回补"应该能对上。
            "stock_total": sum(row["stock"] for row in rows),
            "sold_total": sum(row["sold"] for row in rows),
            "restocked_total": sum(row["restocked"] for row in rows),
        },
        "skus": rows,
        "coupons": _coupon_rows(),
        "orders": _order_counts(),
        "note": "只统计数量，不包含用户名、手机号与地址。",
    }
