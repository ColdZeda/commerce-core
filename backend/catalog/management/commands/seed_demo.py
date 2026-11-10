"""演示数据：幂等写入商品与 SKU。

只在不存在时创建，不覆盖已有价格/库存，避免重跑把演示改价和库存重置掉。
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.models import SKU, Product

CATALOG = [
    (
        "降噪蓝牙耳机",
        "40dB 主动降噪，通勤可用",
        [("EAR-100", "标准版", "399.00", 120), ("EAR-100-PRO", "旗舰版", "599.00", 40)],
    ),
    (
        "机械键盘 87 键",
        "热插拔轴体，PBT 键帽",
        [("KBD-87-BRN", "茶轴", "289.00", 80), ("KBD-87-RED", "红轴", "299.00", 60)],
    ),
    (
        "便携显示器 15.6 寸",
        "1080p IPS，Type-C 供电",
        [("MON-156", "标配", "799.00", 25)],
    ),
    (
        "无线鼠标",
        "静音微动，2.4G + 蓝牙",
        [("MOU-2G", "黑色", "99.00", 200), ("MOU-2G-W", "白色", "109.00", 150)],
    ),
    (
        "USB-C 扩展坞",
        "七合一，带 HDMI",
        [("DOCK-7IN1", "七合一", "219.00", 70)],
    ),
    (
        "桌面显示器支架",
        "单臂气压，17-32 寸",
        [("ARM-S1", "单臂", "259.00", 45)],
    ),
]


class Command(BaseCommand):
    help = "写入演示商品与 SKU（幂等，不覆盖已存在的数据）"

    @transaction.atomic
    def handle(self, *args, **options):
        created_products = 0
        created_skus = 0

        for name, subtitle, skus in CATALOG:
            product, product_created = Product.objects.get_or_create(
                name=name,
                defaults={"subtitle": subtitle},
            )
            created_products += int(product_created)

            for sku_code, title, price, stock in skus:
                _, sku_created = SKU.objects.get_or_create(
                    sku_code=sku_code,
                    defaults={
                        "product": product,
                        "title": title,
                        "price": Decimal(price),
                        "stock": stock,
                    },
                )
                created_skus += int(sku_created)

        self.stdout.write(
            self.style.SUCCESS(
                f"新增商品 {created_products} 个、SKU {created_skus} 个；"
                f"当前商品 {Product.objects.count()} 个、SKU {SKU.objects.count()} 个"
            )
        )
