"""商品与 SKU：价格和库存都落在 SKU 上，商品只负责聚合展示。"""

from django.db import models

from common.models import TimeStampedModel


class Product(TimeStampedModel):
    class Category(models.TextChoices):
        KEYBOARD = "keyboard", "键盘"
        MOUSE = "mouse", "鼠标"
        HEADSET = "headset", "耳机"
        MONITOR = "monitor", "显示器"
        STAND = "stand", "支架"
        DOCK = "dock", "扩展坞"

    name = models.CharField(max_length=120)
    subtitle = models.CharField(max_length=200, blank=True, default="")
    description = models.TextField(blank=True, default="")
    # 封面是随前端一起打包的静态 SVG，只存路径（如 /img/products/kbd-87.svg）；站内没有上传。
    cover = models.CharField(max_length=200, blank=True, default="")
    category = models.CharField(max_length=16, choices=Category.choices, blank=True, default="")
    # 没有真实销量就不编造，"热销"由后台手选；"新品"按 created_at 排。
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "product"
        ordering = ["-id"]
        indexes = [models.Index(fields=["is_active", "-id"], name="idx_product_active_id")]

    def __str__(self) -> str:
        return self.name


class SKU(TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="skus")
    sku_code = models.CharField(max_length=64, unique=True)
    title = models.CharField(max_length=120)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    # 有符号 INT + CHECK：库存不可能为负，靠约束而不是靠 UNSIGNED 溢出报错。
    stock = models.IntegerField(default=0)
    version = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "sku"
        constraints = [
            models.CheckConstraint(condition=models.Q(stock__gte=0), name="ck_sku_stock_non_negative"),
        ]

    def __str__(self) -> str:
        return f"{self.sku_code} {self.title}"
