"""退款：只退本人的已支付整单、只生效一次；库存与券回到下单前，对账看板仍然平。"""

import threading

import pytest
from django.db import connection
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from audit.services import build_report
from catalog.models import SKU
from common.errors import BusinessError
from promotion.models import UserCoupon
from trade.models import Order
from trade.services import cancel_order, close_order, create_order, mark_order_paid, refund_order
from trade.tests.factories import (
    expire_now,
    make_address,
    make_buyer,
    make_sku_stock,
    make_user_coupon,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def buyer():
    return make_buyer()


@pytest.fixture
def sku():
    return make_sku_stock(price="30.00", stock=10)


@pytest.fixture
def auth_client(buyer):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(buyer)}")
    return client


@pytest.fixture
def paid_order(buyer, sku):
    order, _ = create_order(buyer, [{"sku_id": sku.pk, "qty": 2}], address=make_address(buyer))
    mark_order_paid(order.order_no, order.pay_amount, "TRADE-REFUND")
    order.refresh_from_db()
    return order


def test_refund_requires_login(client, paid_order):
    response = client.post(reverse("order-refund", args=[paid_order.order_no]), format="json")

    assert response.status_code == 401


def test_refund_of_another_users_order_is_404(paid_order):
    stranger = make_buyer("stranger")
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(stranger)}")

    response = client.post(reverse("order-refund", args=[paid_order.order_no]), format="json")

    assert response.status_code == 404
    assert Order.objects.get(pk=paid_order.pk).status == Order.Status.PAID


def test_refund_before_payment_conflicts(auth_client, buyer, sku):
    order, _ = create_order(buyer, [{"sku_id": sku.pk, "qty": 1}])

    response = auth_client.post(reverse("order-refund", args=[order.order_no]), format="json")

    assert response.status_code == 409
    assert response.json()["code"] == "ORDER_STATUS_INVALID"
    assert Order.objects.get(pk=order.pk).status == Order.Status.PENDING


def test_refund_returns_stock_and_coupon(buyer, sku):
    user_coupon = make_user_coupon(buyer, threshold="20.00", discount="5.00")
    order, _ = create_order(
        buyer,
        [{"sku_id": sku.pk, "qty": 2}],
        user_coupon_id=user_coupon.pk,
        address=make_address(buyer),
    )
    mark_order_paid(order.order_no, order.pay_amount, "TRADE-REFUND")

    refunded = refund_order(buyer, order.order_no, reason="不想要了")

    assert refunded.status == Order.Status.REFUNDED
    assert refunded.refunded_at is not None
    assert refunded.refund_reason == "不想要了"
    assert SKU.objects.get(pk=sku.pk).stock == 10
    user_coupon.refresh_from_db()
    assert user_coupon.status == UserCoupon.Status.UNUSED


def test_refund_twice_only_restocks_once(buyer, sku, paid_order):
    refund_order(buyer, paid_order.order_no)

    with pytest.raises(BusinessError) as excinfo:
        refund_order(buyer, paid_order.order_no)

    assert excinfo.value.get_codes() == "ORDER_ALREADY_REFUNDED"
    assert SKU.objects.get(pk=sku.pk).stock == 10


def test_cancelled_order_cannot_be_refunded(buyer, sku):
    order, _ = create_order(buyer, [{"sku_id": sku.pk, "qty": 1}])
    cancel_order(buyer, order.order_no)

    with pytest.raises(BusinessError) as excinfo:
        refund_order(buyer, order.order_no)

    # 已取消的单库存已经补过一次，走到这里必须被状态机挡住，不能再补一次。
    assert excinfo.value.get_codes() == "ORDER_STATUS_INVALID"
    assert SKU.objects.get(pk=sku.pk).stock == 10


def test_closed_order_cannot_be_refunded(buyer, sku):
    order, _ = create_order(buyer, [{"sku_id": sku.pk, "qty": 1}])
    expire_now(order)
    close_order(order.order_no)

    with pytest.raises(BusinessError) as excinfo:
        refund_order(buyer, order.order_no)

    assert excinfo.value.get_codes() == "ORDER_STATUS_INVALID"


def test_refund_api_returns_refunded_detail(auth_client, paid_order):
    response = auth_client.post(
        reverse("order-refund", args=[paid_order.order_no]), {"reason": "买错了"}, format="json"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == Order.Status.REFUNDED
    assert body["status_name"] == "refunded"
    assert body["status_label"] == "已退款"
    assert body["refund_reason"] == "买错了"
    assert body["refunded_at"] is not None
    assert len(body["items"]) == 1


def test_order_list_filters_refunded(auth_client, buyer, paid_order):
    refund_order(buyer, paid_order.order_no)

    body = auth_client.get(reverse("order-list"), {"status": "refunded"}).json()

    assert [row["order_no"] for row in body["results"]] == [paid_order.order_no]


def test_audit_stays_balanced_after_refund(buyer, sku, paid_order):
    refund_order(buyer, paid_order.order_no)

    report = build_report()
    row = next(item for item in report["skus"] if item["sku_code"] == sku.sku_code)

    # 退款把量从"已售"挪到"回补"，两条恒等式都得继续成立。
    assert row["sold"] == 0
    assert row["restocked"] == 2
    assert row["stock"] == 10
    assert row["balanced"] is True
    assert report["summary"]["unbalanced"] == 0
    assert report["orders"]["refunded"] == 1


@pytest.mark.concurrency
@pytest.mark.django_db(transaction=True)
def test_concurrent_refunds_only_one_wins():
    buyer = make_buyer()
    sku = make_sku_stock(stock=10)
    order, _ = create_order(buyer, [{"sku_id": sku.pk, "qty": 2}])
    mark_order_paid(order.order_no, order.pay_amount, "TRADE-CONC")
    barrier = threading.Barrier(6)
    outcomes: list[str] = []
    lock = threading.Lock()

    def worker(_):
        barrier.wait()
        try:
            refund_order(buyer, order.order_no)
            result = "refunded"
        except BusinessError as exc:
            result = exc.get_codes()
        connection.close()
        with lock:
            outcomes.append(result)

    threads = [threading.Thread(target=worker, args=(index,)) for index in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert outcomes.count("refunded") == 1
    assert outcomes.count("ORDER_ALREADY_REFUNDED") == 5
    assert SKU.objects.get(pk=sku.pk).stock == 10
