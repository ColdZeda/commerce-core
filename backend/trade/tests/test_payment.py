"""支付：/pay 与回调共用 service、重复支付只生效一次、签名/金额/时间窗校验、关单后不能付。"""

import threading
import time

import pytest
from django.db import connection
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from catalog.models import SKU
from common.errors import BusinessError
from promotion.models import UserCoupon
from trade.models import Order
from trade.payments import sign_payload
from trade.services import close_order, create_order, mark_order_paid
from trade.tests.factories import expire_now, make_buyer, make_sku_stock, make_user_coupon

pytestmark = pytest.mark.django_db


@pytest.fixture
def buyer():
    return make_buyer()


@pytest.fixture
def sku():
    return make_sku_stock(stock=10)


@pytest.fixture
def auth_client(buyer):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(buyer)}")
    return client


@pytest.fixture
def order(buyer, sku):
    return create_order(buyer, [{"sku_id": sku.pk, "qty": 2}])[0]


def signed_payload(order, trade_no="TRADE-1", amount=None, timestamp=None):
    amount = order.pay_amount if amount is None else amount
    timestamp = int(time.time()) if timestamp is None else timestamp
    return {
        "order_no": order.order_no,
        "trade_no": trade_no,
        "amount": f"{amount:.2f}" if hasattr(amount, "quantize") else str(amount),
        "timestamp": timestamp,
        "sign": sign_payload(order.order_no, trade_no, amount, timestamp),
    }


def test_pay_requires_login(client, order):
    response = client.post(reverse("order-pay", args=[order.order_no]), format="json")

    assert response.status_code == 401


@override_settings(ENABLE_MOCK_PAY=True)
def test_pay_marks_paid_and_replays_once(auth_client, order, sku):
    first = auth_client.post(reverse("order-pay", args=[order.order_no]), format="json")
    second = auth_client.post(reverse("order-pay", args=[order.order_no]), format="json")

    assert first.status_code == 200
    assert first.json()["status"] == Order.Status.PAID
    assert second.status_code == 200
    assert second.headers["X-Idempotent-Replay"] == "1"

    order.refresh_from_db()
    assert order.status == Order.Status.PAID
    assert order.paid_at is not None
    # 支付不退券、不回补库存：那是退款流程，本项目不做。
    assert SKU.objects.get(pk=sku.pk).stock == 8


@override_settings(ENABLE_MOCK_PAY=False)
def test_pay_is_blocked_when_switch_is_off(auth_client, order):
    response = auth_client.post(reverse("order-pay", args=[order.order_no]), format="json")

    assert response.status_code == 403
    assert response.json()["code"] == "PAY_NOT_ENABLED"
    assert Order.objects.get(pk=order.pk).status == Order.Status.PENDING


def test_pay_after_close_conflicts(auth_client, order):
    expire_now(order)
    close_order(order.order_no)

    response = auth_client.post(reverse("order-pay", args=[order.order_no]), format="json")

    assert response.status_code == 409
    assert response.json()["code"] == "ORDER_NOT_PAYABLE"


def test_callback_pays_pending_order(client, order):
    response = client.post(reverse("payment-callback"), signed_payload(order), format="json")

    assert response.status_code == 200
    assert response.json()["idempotent"] is False
    assert Order.objects.get(pk=order.pk).status == Order.Status.PAID


def test_callback_is_idempotent(client, order):
    payload = signed_payload(order)
    first = client.post(reverse("payment-callback"), payload, format="json")
    paid_at = Order.objects.get(pk=order.pk).paid_at
    second = client.post(reverse("payment-callback"), payload, format="json")

    assert first.json()["idempotent"] is False
    assert second.status_code == 200
    assert second.json()["idempotent"] is True
    assert Order.objects.get(pk=order.pk).paid_at == paid_at


@pytest.mark.parametrize(
    "sign",
    ["", "0" * 63, "0" * 65, "z" * 64, "中" * 64],
    ids=["empty", "short", "long", "not-hex", "unicode"],
)
def test_callback_rejects_malformed_signature(client, order, sign):
    payload = signed_payload(order)
    payload["sign"] = sign

    response = client.post(reverse("payment-callback"), payload, format="json")

    assert response.status_code == 400
    assert Order.objects.get(pk=order.pk).status == Order.Status.PENDING


def test_callback_rejects_bad_signature(client, order):
    payload = signed_payload(order)
    payload["sign"] = "0" * 64

    response = client.post(reverse("payment-callback"), payload, format="json")

    assert response.status_code == 401
    assert response.json()["code"] == "PAY_SIGN_INVALID"
    assert Order.objects.get(pk=order.pk).status == Order.Status.PENDING


def test_callback_rejects_stale_timestamp(client, order):
    payload = signed_payload(order, timestamp=int(time.time()) - 600)

    response = client.post(reverse("payment-callback"), payload, format="json")

    assert response.status_code == 401
    assert response.json()["code"] == "PAY_SIGN_INVALID"
    assert Order.objects.get(pk=order.pk).status == Order.Status.PENDING


def test_callback_rejects_amount_mismatch(client, order):
    payload = signed_payload(order, amount="1.00")

    response = client.post(reverse("payment-callback"), payload, format="json")

    assert response.status_code == 409
    assert response.json()["code"] == "PAY_AMOUNT_MISMATCH"
    assert Order.objects.get(pk=order.pk).status == Order.Status.PENDING


def test_callback_on_closed_order_conflicts(client, order):
    expire_now(order)
    close_order(order.order_no)

    response = client.post(reverse("payment-callback"), signed_payload(order), format="json")

    assert response.status_code == 409
    assert response.json()["code"] == "ORDER_NOT_PAYABLE"
    assert Order.objects.get(pk=order.pk).status == Order.Status.CLOSED


def test_callback_for_unknown_order_is_404(client, order):
    payload = signed_payload(order)
    payload["order_no"] = "OD20260101000000000000"
    payload["sign"] = sign_payload(
        payload["order_no"], payload["trade_no"], payload["amount"], payload["timestamp"]
    )

    response = client.post(reverse("payment-callback"), payload, format="json")

    assert response.status_code == 404


@pytest.mark.concurrency
@pytest.mark.django_db(transaction=True)
def test_concurrent_callbacks_pay_once():
    buyer = make_buyer()
    sku = make_sku_stock(stock=10)
    order, _ = create_order(buyer, [{"sku_id": sku.pk, "qty": 2}])
    barrier = threading.Barrier(6)
    outcomes: list[bool] = []
    lock = threading.Lock()

    def worker(_):
        barrier.wait()
        try:
            _paid, already = mark_order_paid(order.order_no, order.pay_amount, "TRADE-CONC")
            result = already
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

    assert outcomes.count(False) == 1
    assert outcomes.count(True) == 5
    assert Order.objects.get(pk=order.pk).status == Order.Status.PAID


def test_paying_does_not_touch_coupon_state(buyer, sku):
    user_coupon = make_user_coupon(buyer, threshold="20.00", discount="5.00")
    order, _ = create_order(buyer, [{"sku_id": sku.pk, "qty": 2}], user_coupon_id=user_coupon.pk)

    paid, already = mark_order_paid(order.order_no, order.pay_amount, "TRADE-COUPON")

    assert (paid.status, already) == (Order.Status.PAID, False)
    user_coupon.refresh_from_db()
    assert user_coupon.status == UserCoupon.Status.USED
