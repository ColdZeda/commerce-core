"""后台只读：订单与券在 admin 里只能看，不能改——状态只能由接口的条件更新推进。"""

import pytest
from django.urls import reverse

from promotion.tests.factories import make_coupon
from trade.services import create_order
from trade.tests.factories import make_address, make_buyer, make_sku_stock

pytestmark = pytest.mark.django_db


@pytest.fixture
def order():
    buyer = make_buyer()
    return create_order(buyer, [{"sku_id": make_sku_stock().pk, "qty": 1}], address=make_address(buyer))[0]


def test_order_changelist_is_visible(admin_client):
    assert admin_client.get(reverse("admin:trade_order_changelist")).status_code == 200


def test_order_cannot_be_added(admin_client):
    assert admin_client.get(reverse("admin:trade_order_add")).status_code == 403


def test_order_change_page_is_read_only_and_post_is_forbidden(admin_client, order):
    url = reverse("admin:trade_order_change", args=[order.pk])

    # 只读权限下详情页要能打开（否则连查都查不了），但提交必须被拒。
    assert admin_client.get(url).status_code == 200
    assert admin_client.post(url, {"status": "1"}).status_code == 403


def test_coupon_cannot_be_added_or_changed(admin_client):
    coupon = make_coupon()

    assert admin_client.get(reverse("admin:promotion_coupon_add")).status_code == 403
    assert (
        admin_client.post(
            reverse("admin:promotion_coupon_change", args=[coupon.pk]), {"total_qty": "999"}
        ).status_code
        == 403
    )
