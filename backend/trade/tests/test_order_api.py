"""订单接口契约：创建与重放、列表筛选、越权 404、取消幂等。"""

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from catalog.models import SKU
from promotion.models import UserCoupon
from trade.models import Order
from trade.tests.factories import force_status, make_buyer, make_sku_stock, make_user_coupon

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


def post_order(client, sku, **body):
    payload = {"items": [{"sku_id": sku.pk, "qty": 1}], **body}
    return client.post(reverse("order-list"), payload, format="json")


def test_create_requires_login(client, sku):
    response = client.post(reverse("order-list"), {"items": [{"sku_id": sku.pk, "qty": 1}]}, format="json")

    assert response.status_code == 401
    assert response.json()["code"] == "TOKEN_INVALID"


def test_create_returns_snapshot_and_string_amounts(auth_client, sku):
    response = post_order(auth_client, sku, remark="尽快发货")

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == Order.Status.PENDING
    assert payload["total_amount"] == "30.00"
    assert payload["pay_amount"] == "30.00"
    assert payload["remark"] == "尽快发货"
    assert payload["items"][0]["sku_code"] == sku.sku_code
    assert payload["items"][0]["qty"] == 1
    assert Order.objects.count() == 1


def test_same_client_token_replays_the_first_order(auth_client, sku):
    first = post_order(auth_client, sku, client_token="token-abc")
    second = post_order(auth_client, sku, client_token="token-abc")

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.headers["X-Idempotent-Replay"] == "1"
    assert second.json()["order_no"] == first.json()["order_no"]
    assert Order.objects.count() == 1
    assert SKU.objects.get(pk=sku.pk).stock == 9


def test_duplicate_sku_and_empty_items_are_rejected(auth_client, sku):
    duplicated = auth_client.post(
        reverse("order-list"),
        {"items": [{"sku_id": sku.pk, "qty": 1}, {"sku_id": sku.pk, "qty": 2}]},
        format="json",
    )
    empty = auth_client.post(reverse("order-list"), {"items": []}, format="json")

    assert duplicated.status_code == 400
    assert duplicated.json()["code"] == "VALIDATION_ERROR"
    assert empty.status_code == 400


def test_list_only_shows_own_orders_and_filters_by_status(auth_client, buyer, sku):
    mine = post_order(auth_client, sku).json()
    force_status(Order.objects.get(order_no=mine["order_no"]), Order.Status.PAID)
    post_order(auth_client, sku)

    stranger = make_buyer(username="stranger")
    stranger_order = Order.objects.create(
        order_no="OD20260101000000000001",
        user=stranger,
        total_amount="1.00",
        pay_amount="1.00",
        expire_at=timezone.now(),
    )

    everything = auth_client.get(reverse("order-list")).json()
    paid_only = auth_client.get(reverse("order-list"), {"status": "paid"}).json()
    invalid = auth_client.get(reverse("order-list"), {"status": "unknown"})

    assert everything["count"] == 2
    assert stranger_order.order_no not in {row["order_no"] for row in everything["results"]}
    assert [row["order_no"] for row in paid_only["results"]] == [mine["order_no"]]
    assert invalid.status_code == 400


def test_detail_of_someone_elses_order_is_404(auth_client, sku):
    stranger = make_buyer(username="stranger")
    stranger_order = Order.objects.create(
        order_no="OD20260101000000000002",
        user=stranger,
        total_amount="1.00",
        pay_amount="1.00",
        expire_at=timezone.now(),
    )

    response = auth_client.get(reverse("order-detail", args=[stranger_order.order_no]))

    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_cancel_restocks_and_returns_coupon_once(auth_client, buyer, sku):
    user_coupon = make_user_coupon(buyer, threshold="20.00", discount="5.00")
    created = post_order(auth_client, sku, qty=2, user_coupon_id=user_coupon.pk).json()

    first = auth_client.post(
        reverse("order-cancel", args=[created["order_no"]]), {"reason": "不想要了"}, format="json"
    )
    second = auth_client.post(reverse("order-cancel", args=[created["order_no"]]), format="json")

    assert first.status_code == 200
    assert first.json()["status"] == Order.Status.CANCELLED
    assert first.json()["cancel_reason"] == "不想要了"
    assert second.status_code == 200
    assert SKU.objects.get(pk=sku.pk).stock == 10
    user_coupon.refresh_from_db()
    assert user_coupon.status == UserCoupon.Status.UNUSED


def test_cancel_of_paid_order_conflicts(auth_client, sku):
    order_no = post_order(auth_client, sku).json()["order_no"]
    force_status(Order.objects.get(order_no=order_no), Order.Status.PAID)

    response = auth_client.post(reverse("order-cancel", args=[order_no]), format="json")

    assert response.status_code == 409
    assert response.json()["code"] == "ORDER_STATUS_INVALID"
    assert SKU.objects.get(pk=sku.pk).stock == 9
