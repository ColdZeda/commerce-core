"""购物车接口：同 SKU 只留一行、数量受库存约束、别人的行一律看不到。"""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from catalog.tests.factories import make_product, make_sku

from ..models import CartItem

pytestmark = pytest.mark.django_db

User = get_user_model()


@pytest.fixture
def buyer():
    return User.objects.create_user(username="cart-buyer", password="pw-cart-12345")


@pytest.fixture
def auth_client(buyer):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(buyer)}")
    return client


@pytest.fixture
def sku():
    return make_sku(make_product(name="购物车商品"), price="100.00", stock=10)


def add(client, sku, qty=1):
    return client.post(reverse("cart-items"), {"sku_id": sku.pk, "qty": qty}, format="json")


def test_cart_requires_login(client, sku):
    assert client.get(reverse("cart-items")).status_code == 401
    assert add(client, sku).status_code == 401


def test_add_creates_single_row_and_returns_snapshot(auth_client, buyer, sku):
    response = add(auth_client, sku, qty=2)

    assert response.status_code == 201
    payload = response.json()
    assert payload["total_qty"] == 2
    assert payload["total_amount"] == "200.00"
    assert payload["items"][0]["product_name"] == "购物车商品"
    assert payload["items"][0]["subtotal"] == "200.00"
    assert payload["items"][0]["available"] is True
    assert CartItem.objects.filter(user=buyer).count() == 1


def test_adding_same_sku_accumulates_instead_of_duplicating(auth_client, buyer, sku):
    add(auth_client, sku, qty=2)
    payload = add(auth_client, sku, qty=3).json()

    assert CartItem.objects.filter(user=buyer).count() == 1
    assert payload["items"][0]["qty"] == 5
    assert payload["total_qty"] == 5


def test_add_beyond_stock_is_rejected_and_leaves_cart_untouched(auth_client, sku):
    response = add(auth_client, sku, qty=11)

    assert response.status_code == 409
    assert response.json()["code"] == "STOCK_NOT_ENOUGH"
    assert CartItem.objects.count() == 0


def test_accumulation_beyond_stock_rolls_back(auth_client, sku):
    add(auth_client, sku, qty=6)
    response = add(auth_client, sku, qty=6)

    assert response.status_code == 409
    assert CartItem.objects.get().qty == 6


def test_add_off_shelf_sku_is_rejected(auth_client):
    product = make_product(name="已下架")
    sku = make_sku(product, price="10.00", is_active=False)

    response = add(auth_client, sku)

    assert response.status_code == 409
    assert response.json()["code"] == "PRODUCT_OFF_SHELF"


def test_add_unknown_sku_is_400(auth_client):
    response = auth_client.post(reverse("cart-items"), {"sku_id": 999_999, "qty": 1}, format="json")

    assert response.status_code == 400
    assert "sku_id" in response.json()["detail"]


@pytest.mark.parametrize("qty", [0, -1, 1000])
def test_add_rejects_out_of_range_qty(auth_client, sku, qty):
    response = add(auth_client, sku, qty=qty)

    assert response.status_code == 400


def test_patch_changes_qty_and_delete_removes_row(auth_client, sku):
    item_id = add(auth_client, sku, qty=1).json()["items"][0]["id"]

    patched = auth_client.patch(reverse("cart-item-detail", args=[item_id]), {"qty": 4}, format="json")
    assert patched.status_code == 200
    assert patched.json()["items"][0]["qty"] == 4

    removed = auth_client.delete(reverse("cart-item-detail", args=[item_id]))
    assert removed.status_code == 200
    assert removed.json()["items"] == []


def test_patch_beyond_stock_is_rejected(auth_client, sku):
    item_id = add(auth_client, sku, qty=1).json()["items"][0]["id"]

    response = auth_client.patch(reverse("cart-item-detail", args=[item_id]), {"qty": 99}, format="json")

    assert response.status_code == 409
    assert CartItem.objects.get().qty == 1


def test_other_users_item_looks_missing(sku):
    owner = User.objects.create_user(username="owner", password="pw-owner-12345")
    CartItem.objects.create(user=owner, sku=sku, qty=1)
    item = CartItem.objects.get()

    owner_client = APIClient()
    owner_client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(owner)}")
    assert owner_client.get(reverse("cart-items")).json()["total_qty"] == 1

    stranger = User.objects.create_user(username="stranger", password="pw-stranger-123")
    stranger_client = APIClient()
    stranger_client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(stranger)}")

    assert stranger_client.delete(reverse("cart-item-detail", args=[item.pk])).status_code == 404
    assert (
        stranger_client.patch(
            reverse("cart-item-detail", args=[item.pk]), {"qty": 2}, format="json"
        ).status_code
        == 404
    )
    assert CartItem.objects.get().qty == 1


def test_available_flips_false_when_stock_drops(auth_client, sku):
    add(auth_client, sku, qty=5)
    sku.stock = 3
    sku.save(update_fields=["stock"])

    payload = auth_client.get(reverse("cart-items")).json()

    assert payload["items"][0]["available"] is False
