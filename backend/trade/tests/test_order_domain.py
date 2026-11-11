"""下单主干的服务层行为：金额、库存、券、快照、单号。"""

import re
from datetime import timedelta
from decimal import Decimal

import pytest

from catalog.models import SKU
from common.errors import BusinessError
from promotion.models import UserCoupon
from trade.models import Order
from trade.services import create_order
from trade.tests.factories import make_buyer, make_sku_stock, make_user_coupon

pytestmark = pytest.mark.django_db


@pytest.fixture
def buyer():
    return make_buyer()


@pytest.fixture
def sku():
    return make_sku_stock(price="30.00", stock=10)


def place(user, sku, qty=1, **kwargs):
    items = [{"sku_id": sku.pk, "qty": qty}]
    return create_order(user, items, **kwargs)[0]


def test_total_discount_and_pay_are_computed_by_server(buyer, sku):
    user_coupon = make_user_coupon(buyer, threshold="50.00", discount="10.00")

    order = place(buyer, sku, qty=2, user_coupon_id=user_coupon.pk)

    assert order.total_amount == Decimal("60.00")
    assert order.discount_amount == Decimal("10.00")
    assert order.pay_amount == Decimal("50.00")
    user_coupon.refresh_from_db()
    assert user_coupon.status == UserCoupon.Status.USED
    assert user_coupon.used_at is not None


def test_coupon_below_threshold_changes_nothing(buyer, sku):
    user_coupon = make_user_coupon(buyer, threshold="50.00", discount="10.00")

    with pytest.raises(BusinessError) as excinfo:
        place(buyer, sku, qty=1, user_coupon_id=user_coupon.pk)

    assert excinfo.value.get_codes() == "COUPON_NOT_USABLE"
    user_coupon.refresh_from_db()
    assert user_coupon.status == UserCoupon.Status.UNUSED
    assert SKU.objects.get(pk=sku.pk).stock == 10
    assert Order.objects.count() == 0


def test_discount_never_exceeds_order_total(buyer, sku):
    user_coupon = make_user_coupon(buyer, threshold="10.00", discount="100.00")

    order = place(buyer, sku, qty=1, user_coupon_id=user_coupon.pk)

    assert order.discount_amount == Decimal("30.00")
    assert order.pay_amount == Decimal("0.00")


def test_coupon_owned_by_someone_else_is_rejected(buyer, sku):
    stranger = make_buyer(username="stranger")
    user_coupon = make_user_coupon(stranger, threshold="10.00", discount="5.00")

    with pytest.raises(BusinessError) as excinfo:
        place(buyer, sku, qty=1, user_coupon_id=user_coupon.pk)

    assert excinfo.value.get_codes() == "COUPON_NOT_USABLE"
    user_coupon.refresh_from_db()
    assert user_coupon.status == UserCoupon.Status.UNUSED


def test_stock_shortage_creates_no_order(buyer, sku):
    with pytest.raises(BusinessError) as excinfo:
        place(buyer, sku, qty=11)

    assert excinfo.value.get_codes() == "STOCK_NOT_ENOUGH"
    assert SKU.objects.get(pk=sku.pk).stock == 10
    assert Order.objects.count() == 0


def test_off_shelf_and_unknown_sku_are_rejected(buyer):
    off_shelf = make_sku_stock(stock=5, is_active=False)

    for sku_id in (off_shelf.pk, 999999):
        with pytest.raises(BusinessError) as excinfo:
            create_order(buyer, [{"sku_id": sku_id, "qty": 1}])
        assert excinfo.value.get_codes() == "PRODUCT_OFF_SHELF"


def test_snapshot_keeps_history_after_price_change(buyer, sku):
    order = place(buyer, sku, qty=2)

    SKU.objects.filter(pk=sku.pk).update(price=Decimal("999.00"), title="改过的规格", sku_code="SKU-CHANGED")
    item = order.items.get()

    assert item.unit_price == Decimal("30.00")
    assert item.subtotal == Decimal("60.00")
    assert item.title == "默认规格"
    assert order.pay_amount == Decimal("60.00")


def test_stock_and_version_move_together(buyer, sku):
    place(buyer, sku, qty=3)

    refreshed = SKU.objects.get(pk=sku.pk)
    assert refreshed.stock == 7
    assert refreshed.version == 1


def test_expire_at_uses_the_configured_window(buyer, sku):
    order = place(buyer, sku)

    assert abs(order.expire_at - order.created_at - timedelta(minutes=15)) < timedelta(seconds=5)


def test_order_no_is_time_prefixed_and_random(buyer, sku):
    first = place(buyer, sku)
    second = place(buyer, sku)

    assert re.fullmatch(r"OD\d{20}", first.order_no)
    assert first.order_no != second.order_no
