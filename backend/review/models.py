"""评论：一条订单明细只能评一次，评分 1–5。"""

from django.conf import settings
from django.db import models

from common.models import TimeStampedModel


class Review(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reviews")
    # 一对一就是"一条明细只能评一次"的硬约束，不靠应用层判重。
    order_item = models.OneToOneField("trade.OrderItem", on_delete=models.CASCADE, related_name="review")
    # 冗余存商品：商品页按它查，不必每次都从 order_item → sku 绕两跳。
    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField()
    content = models.CharField(max_length=500, blank=True, default="")

    class Meta:
        db_table = "review"
        ordering = ["-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(rating__gte=1) & models.Q(rating__lte=5),
                name="ck_review_rating_range",
            ),
        ]
        indexes = [models.Index(fields=["product", "-id"], name="idx_review_product_id")]

    def __str__(self) -> str:
        return f"{self.product_id} {self.rating}星"
