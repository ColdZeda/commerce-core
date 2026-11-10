"""券：固定满减，不叠加、不续期；每人每券一张。"""

from django.conf import settings
from django.db import models

from common.models import TimeStampedModel


class Coupon(TimeStampedModel):
    name = models.CharField(max_length=120)
    threshold_amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2)
    total_qty = models.PositiveIntegerField()
    issued_qty = models.PositiveIntegerField(default=0)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "coupon"
        indexes = [models.Index(fields=["is_active", "end_at"], name="idx_coupon_active_end")]
        constraints = [
            # 超发只能靠这个约束兜底，领券流程里的条件更新是第一道闸。
            models.CheckConstraint(
                condition=models.Q(issued_qty__gte=0) & models.Q(issued_qty__lte=models.F("total_qty")),
                name="ck_coupon_issued_within_total",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class UserCoupon(models.Model):
    class Status(models.IntegerChoices):
        UNUSED = 0, "未使用"
        USED = 1, "已使用"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="user_coupons")
    coupon = models.ForeignKey(Coupon, on_delete=models.PROTECT, related_name="user_coupons")
    status = models.SmallIntegerField(choices=Status.choices, default=Status.UNUSED)
    received_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user_coupon"
        constraints = [models.UniqueConstraint(fields=["user", "coupon"], name="uq_user_coupon_user_coupon")]
        indexes = [models.Index(fields=["user", "status"], name="idx_user_coupon_user_status")]

    def __str__(self) -> str:
        return f"{self.user_id}-{self.coupon_id}"
