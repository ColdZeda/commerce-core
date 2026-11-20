"""购物车：一行就是"某人要买某个 SKU 几个"，不存价格——价格永远以 SKU 为准。"""

from django.conf import settings
from django.db import models

from catalog.models import SKU
from common.models import TimeStampedModel


class CartItem(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cart_items")
    # 同一 SKU 在同一个人的车里只留一行，加购等于改数量，唯一索引兜住并发。
    sku = models.ForeignKey(SKU, on_delete=models.CASCADE, related_name="cart_items")
    qty = models.PositiveIntegerField(default=1)
    # 勾选状态存在服务端：换设备、刷新页面都要和上次一致，结算只处理勾中的行。
    selected = models.BooleanField(default=True)

    class Meta:
        db_table = "cart_item"
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(fields=["user", "sku"], name="uq_cart_item_user_sku"),
            models.CheckConstraint(condition=models.Q(qty__gte=1), name="ck_cart_item_qty_positive"),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}-{self.sku_id}x{self.qty}"
