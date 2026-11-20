"""从购物车结算：与立即购买共用同一张单，成功后才清车。"""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from cart.models import CartItem
from trade.models import Order
from trade.tests.factories import make_buyer, make_sku_stock

pytestmark = pytest.mark.django_db


@pytest.fixture
def buyer():
    return make_buyer()


@pytest.fixture
def auth_client(buyer):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(buyer)}")
    return client


def add_to_cart(client, sku, qty=1):
    client.post(reverse("cart-items"), {"sku_id": sku.pk, "qty": qty}, format="json")


def checkout(client, **body):
    return client.post(reverse("order-list"), {"from_cart": True, **body}, format="json")


def test_checkout_creates_order_from_cart_and_clears_it(auth_client, buyer):
    first = make_sku_stock(price="30.00", stock=10)
    second = make_sku_stock(price="20.00", stock=5)
    add_to_cart(auth_client, first, qty=2)
    add_to_cart(auth_client, second, qty=1)

    response = checkout(auth_client)

    assert response.status_code == 201
    body = response.json()
    assert body["total_amount"] == "80.00"
    assert {item["sku_code"] for item in body["items"]} == {first.sku_code, second.sku_code}
    assert Order.objects.filter(user=buyer).count() == 1
    assert CartItem.objects.filter(user=buyer).count() == 0


def test_empty_cart_is_rejected(auth_client):
    response = checkout(auth_client)

    assert response.status_code == 409
    assert response.json()["code"] == "CART_EMPTY"
    assert Order.objects.count() == 0


def test_from_cart_with_items_is_rejected(auth_client):
    sku = make_sku_stock(price="30.00", stock=10)

    response = checkout(auth_client, items=[{"sku_id": sku.pk, "qty": 1}])

    assert response.status_code == 400
    assert "items" in response.json()["detail"]


def test_cart_line_beyond_stock_keeps_cart_after_failure(auth_client):
    sku = make_sku_stock(price="30.00", stock=10)
    add_to_cart(auth_client, sku, qty=3)
    # 加购之后库存被别人买走一部分，结算时必须失败且车不能被清掉。
    sku.stock = 1
    sku.save(update_fields=["stock"])

    response = checkout(auth_client)

    assert response.status_code == 409
    assert response.json()["code"] == "STOCK_NOT_ENOUGH"
    assert CartItem.objects.count() == 1
    assert Order.objects.count() == 0


def test_replay_does_not_clear_items_added_afterwards(auth_client):
    sku = make_sku_stock(price="30.00", stock=10)
    add_to_cart(auth_client, sku, qty=1)

    first = checkout(auth_client, client_token="cart-token-1")
    add_to_cart(auth_client, sku, qty=2)
    second = checkout(auth_client, client_token="cart-token-1")

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["order_no"] == first.json()["order_no"]
    # 重放的是上一单，后来加的两件还留在车里。
    item = CartItem.objects.get()
    assert item.qty == 2
