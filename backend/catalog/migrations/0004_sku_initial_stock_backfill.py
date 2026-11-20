"""给已有 SKU 补库存基线：初始 = 当前库存 + 净已售。

净已售 = 待支付/已支付的明细数量之和；已取消/已关闭的订单已经把库存回补过，
所以要从"总明细"里分出去，不能直接拿当前库存加全部明细。
"""

from django.db import migrations
from django.db.models import Q, Sum


def backfill(apps, schema_editor):
    SKU = apps.get_model("catalog", "SKU")
    OrderItem = apps.get_model("trade", "OrderItem")

    net_sold = {
        row["sku_id"]: row["total"]
        for row in OrderItem.objects.filter(sku__isnull=False)
        .exclude(order__status__in=[2, 3])
        .values("sku_id")
        .annotate(total=Sum("qty"))
    }

    for sku in SKU.objects.all().only("id", "stock", "initial_stock"):
        sku.initial_stock = sku.stock + net_sold.get(sku.id, 0)
        sku.save(update_fields=["initial_stock"])


def noop(apps, schema_editor):
    """回滚不回填：initial_stock 丢回 0 即可，历史数据由下一次部署重建。"""


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0003_sku_initial_stock"),
        # 回填要读 order_item，得等订单表建好；跨 app 依赖不影响 catalog 的唯一叶子节点。
        ("trade", "0002_order_address_snapshot"),
    ]

    operations = [migrations.RunPython(backfill, noop)]
