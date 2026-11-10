"""订单与明细：明细保存下单时的商品快照，历史订单不受后续改价影响。"""

from decimal import Decimal

from django.conf import settings
from django.db import models

from common.models import TimeStampedModel


class Order(TimeStampedModel):
    class Status(models.IntegerChoices):
        PENDING = 0, "待支付"
        PAID = 1, "已支付"
        CANCELLED = 2, "已取消"
        CLOSED = 3, "已关闭"

    order_no = models.CharField(max_length=32, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders")
    status = models.SmallIntegerField(choices=Status.choices, default=Status.PENDING)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    pay_amount = models.DecimalField(max_digits=10, decimal_places=2)
    user_coupon = models.ForeignKey(
        "promotion.UserCoupon",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="orders",
    )
    expire_at = models.DateTimeField()
    paid_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.CharField(max_length=200, blank=True, default="")
    client_token = models.CharField(max_length=64, null=True, blank=True)
    remark = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        db_table = "order"
        indexes = [
            models.Index(fields=["user", "-created_at"], name="idx_order_user_created"),
            models.Index(fields=["status", "expire_at"], name="idx_order_status_expire"),
        ]
        constraints = [
            # 客户端重试靠它兜底；client_token 为 NULL 时 MySQL 允许任意多行。
            models.UniqueConstraint(fields=["user", "client_token"], name="uq_order_user_client_token"),
        ]

    def __str__(self) -> str:
        return self.order_no


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    sku = models.ForeignKey(
        "catalog.SKU",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="order_items",
    )
    sku_code = models.CharField(max_length=64)
    title = models.CharField(max_length=120)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    qty = models.PositiveIntegerField()
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "order_item"
        constraints = [
            models.CheckConstraint(condition=models.Q(qty__gt=0), name="ck_order_item_qty_positive"),
        ]

    def __str__(self) -> str:
        return f"{self.sku_code} x{self.qty}"
