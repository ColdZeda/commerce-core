"""演示订单与评价：用真实 service 把五种订单状态各走一遍，跑完自动对账。

单号固定成 ODDEMO 前缀：重跑按单号跳过，既不重复消耗库存，也不会和线上真实订单撞号。
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from address.models import Address
from audit.services import build_report
from catalog.models import SKU
from review.models import Review
from review.services import create_reviews
from trade.models import Order
from trade.services import cancel_order, close_order, create_order, mark_order_paid, refund_order

DEMO_USERNAME = "demo"
DEMO_PAID_ORDER = "ODDEMO0002"
DEMO_ADDRESS = {
    "receiver": "演示收货人",
    "phone": "13800138000",
    "region": "广东省 深圳市 南山区",
    "detail": "科技园 1 号 A 座 801",
}
DEMO_REVIEWS = (
    (5, "键盘手感很稳，键帽用了两周也不打油。"),
    (4, "整体满意，物流比预计慢了一天。"),
)


def _pay(order: Order) -> None:
    mark_order_paid(order.order_no, order.pay_amount, "DEMO")


def _cancel(order: Order) -> None:
    cancel_order(order.user, order.order_no, reason="演示：下单后反悔")


def _close(order: Order) -> None:
    # 关单要"已过期"才成立，演示单直接把它推到 expire_at 之后。
    close_order(order.order_no, now=order.expire_at + timedelta(minutes=1))


def _refund(order: Order) -> None:
    _pay(order)
    order.refresh_from_db()
    refund_order(order.user, order.order_no, reason="演示：七天内无理由退款")


DEMO_ORDERS = (
    ("ODDEMO0001", None),
    ("ODDEMO0002", _pay),
    ("ODDEMO0003", _cancel),
    ("ODDEMO0004", _close),
    ("ODDEMO0005", _refund),
)


class Command(BaseCommand):
    help = "写入演示订单与评价（待支付/已支付/已取消/已关闭/已退款），跑完自动对账。"

    @transaction.atomic
    def handle(self, *args, **options):
        user = get_user_model().objects.filter(username=DEMO_USERNAME).first()
        if user is None:
            raise CommandError(
                f"演示账号 {DEMO_USERNAME} 不存在，先跑 create_demo_user --username {DEMO_USERNAME}"
            )

        skus = list(
            SKU.objects.filter(is_active=True, product__is_active=True, stock__gte=1).order_by("pk")[:6]
        )
        if not skus:
            raise CommandError("没有可售的 SKU，先跑 seed_demo")

        address = self._address(user)
        created = 0
        for index, (order_no, finish) in enumerate(DEMO_ORDERS):
            if Order.objects.filter(order_no=order_no).exists():
                continue
            order = self._place(user, address, self._items(skus, index), order_no)
            if finish is not None:
                finish(order)
            created += 1

        reviews = self._reviews(user)
        self._reconcile()
        self.stdout.write(
            self.style.SUCCESS(
                f"新增演示订单 {created} 个、评价 {reviews} 条；"
                f"当前订单 {Order.objects.count()} 个、评价 {Review.objects.count()} 条"
            )
        )

    def _address(self, user) -> Address:
        address = Address.objects.filter(user=user).order_by("-is_default", "id").first()
        if address is not None:
            return address
        return Address.objects.create(user=user, is_default=True, **DEMO_ADDRESS)

    def _items(self, skus: list[SKU], index: int) -> list[dict]:
        first = skus[(index * 2) % len(skus)]
        if len(skus) == 1:
            return [{"sku_id": first.pk, "qty": 1}]
        second = skus[(index * 2 + 1) % len(skus)]
        # 一单两行、每行一件：同一 SKU 只出现一次，库存校验才不会被重复行绕过。
        return [{"sku_id": first.pk, "qty": 1}, {"sku_id": second.pk, "qty": 1}]

    def _place(self, user, address, items: list[dict], order_no: str) -> Order:
        order, _ = create_order(user, items, address=address)
        # 单号由生成器给出，这里换成固定演示号：重跑靠它判断"这一单已经造过了"。
        Order.objects.filter(pk=order.pk).update(order_no=order_no)
        order.refresh_from_db()
        return order

    def _reviews(self, user) -> int:
        order = Order.objects.filter(order_no=DEMO_PAID_ORDER, status=Order.Status.PAID).first()
        if order is None:
            return 0
        items = list(order.items.filter(review__isnull=True).order_by("id")[: len(DEMO_REVIEWS)])
        if not items:
            return 0
        entries = [
            {"order_item_id": item.pk, "rating": rating, "content": content}
            for item, (rating, content) in zip(items, DEMO_REVIEWS, strict=True)
        ]
        return len(create_reviews(user, order.order_no, entries))

    def _reconcile(self) -> None:
        report = build_report()
        unbalanced = [row["sku_code"] for row in report["skus"] if not row["balanced"]]
        if unbalanced:
            raise CommandError(f"对账不平的 SKU：{', '.join(unbalanced)}；先查清库存再跑 seed")
        self.stdout.write(f"对账：{report['summary']['skus']} 个 SKU，unbalanced=0")
