"""测试数据工厂：只造断言需要的最小字段，演示数据走 seed_demo。"""

from decimal import Decimal
from uuid import uuid4

from catalog.models import SKU, Product


def make_product(name="测试商品", is_active=True, **kwargs):
    return Product.objects.create(name=name, is_active=is_active, **kwargs)


def make_sku(product, sku_code=None, price="99.00", stock=10, is_active=True, **kwargs):
    return SKU.objects.create(
        product=product,
        sku_code=sku_code or f"SKU-{uuid4().hex[:8]}",
        title="默认规格",
        price=Decimal(price),
        stock=stock,
        is_active=is_active,
        **kwargs,
    )
