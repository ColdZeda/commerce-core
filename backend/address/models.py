"""收货地址：省市区只是一段文本，不做级联，也不引入行政区数据。"""

from django.conf import settings
from django.db import models

from common.models import TimeStampedModel


class Address(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="addresses")
    receiver = models.CharField(max_length=40)
    phone = models.CharField(max_length=20)
    # 形如"广东省 深圳市 南山区"，由用户自己填；下单时整段快照进订单。
    region = models.CharField(max_length=120)
    detail = models.CharField(max_length=200)
    is_default = models.BooleanField(default=False)

    class Meta:
        db_table = "address"
        ordering = ["-is_default", "-id"]

    def __str__(self) -> str:
        return f"{self.receiver} {self.region}{self.detail}"

    def snapshot(self) -> dict:
        """下单时的地址副本：只留展示需要的字段，不再引用这张表。"""
        return {
            "receiver": self.receiver,
            "phone": self.phone,
            "region": self.region,
            "detail": self.detail,
        }
