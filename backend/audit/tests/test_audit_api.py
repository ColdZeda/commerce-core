"""对账看板：平时是平的，把库存改坏之后必须能看出来（否则这块板子没有意义）。"""

import pytest
from django.urls import reverse

from catalog.models import SKU
from trade.services import cancel_order, close_order, create_order
from trade.tests.factories import expire_now, make_address, make_buyer, make_sku_stock

pytestmark = pytest.mark.django_db


@pytest.fixture
def buyer():
    return make_buyer()


def row_for(report, sku):
    return next(row for row in report["skus"] if row["sku_code"] == sku.sku_code)


def test_audit_is_public_and_balanced_right_after_seeding(client):
    sku = make_sku_stock(price="10.00", stock=8)

    response = client.get(reverse("audit"))

    assert response.status_code == 200
    report = response.json()
    row = row_for(report, sku)
    assert row["initial"] == 8
    assert row["stock"] == 8
    assert row["sold"] == 0
    assert row["balanced"] is True
    assert report["summary"]["balanced"] is True


def test_sold_quantity_reduces_stock_and_keeps_balance(client, buyer):
    sku = make_sku_stock(price="10.00", stock=8)
    create_order(buyer, [{"sku_id": sku.pk, "qty": 3}], address=make_address(buyer))

    row = row_for(client.get(reverse("audit")).json(), sku)

    assert row["sold"] == 3
    assert row["stock"] == 5
    assert row["items_total"] == 3
    assert row["balanced"] is True


def test_cancelled_order_moves_volume_to_restocked(client, buyer):
    sku = make_sku_stock(price="10.00", stock=8)
    order = create_order(buyer, [{"sku_id": sku.pk, "qty": 2}], address=make_address(buyer))[0]
    cancel_order(buyer, order.order_no, reason="测试")

    row = row_for(client.get(reverse("audit")).json(), sku)

    assert row["sold"] == 0
    assert row["restocked"] == 2
    assert row["stock"] == 8
    assert row["items_total"] == 2
    assert row["balanced"] is True


def test_manual_stock_edit_shows_up_as_unbalanced(client):
    sku = make_sku_stock(price="10.00", stock=8)
    # 绕过接口直接改库存：这正是看板要抓的那种"没有留痕的改动"。
    SKU.objects.filter(pk=sku.pk).update(stock=99)

    report = client.get(reverse("audit")).json()
    row = row_for(report, sku)

    assert row["balanced"] is False
    assert row["diff"] == 91
    assert report["summary"]["unbalanced"] == 1
    assert report["summary"]["balanced"] is False


def test_coupon_and_order_counts(client, buyer):
    from promotion.models import UserCoupon
    from promotion.services import claim_coupon
    from promotion.tests.factories import make_coupon

    coupon = make_coupon(name="满 10 减 1", total_qty=5)
    claim_coupon(buyer, coupon.pk)
    UserCoupon.objects.filter(user=buyer).update(status=UserCoupon.Status.USED)

    sku = make_sku_stock()
    create_order(buyer, [{"sku_id": sku.pk, "qty": 1}], address=make_address(buyer))

    report = client.get(reverse("audit")).json()

    assert report["coupons"][0] == {"name": "满 10 减 1", "issued": 1, "total": 5, "used": 1}
    assert report["orders"]["pending"] == 1
    assert report["orders"]["total"] == 1


def test_report_does_not_leak_user_data(client, buyer):
    sku = make_sku_stock()
    create_order(buyer, [{"sku_id": sku.pk, "qty": 1}], address=make_address(buyer, receiver="张三"))

    body = client.get(reverse("audit")).content.decode()

    assert "buyer" not in body
    assert "13800138000" not in body
    assert "张三" not in body


def test_closed_orders_count_as_restocked(client, buyer):
    sku = make_sku_stock(price="10.00", stock=5)
    order = create_order(buyer, [{"sku_id": sku.pk, "qty": 2}], address=make_address(buyer))[0]
    # 走真实的关单路径：它会把库存补回去，直接改状态是不会有 restock 的。
    expire_now(order)
    close_order(order.order_no)

    row = row_for(client.get(reverse("audit")).json(), sku)

    assert row["restocked"] == 2
    assert row["stock"] == 5
    assert row["balanced"] is True
