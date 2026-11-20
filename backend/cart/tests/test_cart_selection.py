"""逐行勾选：勾选状态存服务端，结算只处理勾中的行。"""

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
    return User.objects.create_user(username="pick-buyer", password="pw-pick-12345")


@pytest.fixture
def auth_client(buyer):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(buyer)}")
    return client


@pytest.fixture
def skus():
    product = make_product(name="勾选商品")
    return [make_sku(product, price="10.00", stock=20), make_sku(product, price="20.00", stock=20)]


def add(client, sku, qty=1):
    return client.post(reverse("cart-items"), {"sku_id": sku.pk, "qty": qty}, format="json")


def test_new_item_is_selected_and_snapshot_totals_match(auth_client, skus):
    payload = add(auth_client, skus[0], qty=2).json()

    assert payload["items"][0]["selected"] is True
    assert payload["selected_qty"] == 2
    assert payload["selected_amount"] == "20.00"


def test_unselect_updates_selected_totals_not_total_qty(auth_client, skus):
    add(auth_client, skus[0], qty=2)
    add(auth_client, skus[1], qty=1)
    item_id = CartItem.objects.filter(sku=skus[0]).get().id

    payload = auth_client.patch(
        reverse("cart-item-detail", args=[item_id]), {"selected": False}, format="json"
    ).json()

    assert payload["total_qty"] == 3
    assert payload["total_amount"] == "40.00"
    assert payload["selected_qty"] == 1
    assert payload["selected_amount"] == "20.00"


def test_select_all_toggles_every_row(auth_client, skus):
    add(auth_client, skus[0], qty=1)
    add(auth_client, skus[1], qty=1)

    cleared = auth_client.patch(reverse("cart-items"), {"selected": False}, format="json").json()
    assert cleared["selected_qty"] == 0
    assert cleared["selected_amount"] == "0.00"
    assert CartItem.objects.filter(selected=False).count() == 2

    restored = auth_client.patch(reverse("cart-items"), {"selected": True}, format="json").json()
    assert restored["selected_qty"] == 2
    assert restored["selected_amount"] == "30.00"


def test_patch_requires_at_least_one_field(auth_client, skus):
    item_id = add(auth_client, skus[0]).json()["items"][0]["id"]

    response = auth_client.patch(reverse("cart-item-detail", args=[item_id]), {}, format="json")

    assert response.status_code == 400


def test_patch_can_change_qty_and_selection_together(auth_client, skus):
    item_id = add(auth_client, skus[0]).json()["items"][0]["id"]

    payload = auth_client.patch(
        reverse("cart-item-detail", args=[item_id]), {"qty": 4, "selected": False}, format="json"
    ).json()

    assert payload["items"][0]["qty"] == 4
    assert payload["items"][0]["selected"] is False


def test_other_users_row_cannot_be_selected(skus):
    owner = User.objects.create_user(username="pick-owner", password="pw-pick-owner-1")
    item = CartItem.objects.create(user=owner, sku=skus[0], qty=1)
    stranger = User.objects.create_user(username="pick-stranger", password="pw-pick-str2")
    stranger_client = APIClient()
    stranger_client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(stranger)}")

    response = stranger_client.patch(
        reverse("cart-item-detail", args=[item.pk]), {"selected": False}, format="json"
    )

    assert response.status_code == 404
    assert CartItem.objects.get().selected is True


def test_off_shelf_row_can_still_be_unselected(auth_client, skus):
    item_id = add(auth_client, skus[0]).json()["items"][0]["id"]
    sku = skus[0]
    sku.is_active = False
    sku.save(update_fields=["is_active"])

    # 下架的行不让改数量，但必须能让用户取消勾选，否则结算永远卡住。
    assert (
        auth_client.patch(reverse("cart-item-detail", args=[item_id]), {"qty": 2}, format="json").status_code
        == 409
    )
    assert (
        auth_client.patch(
            reverse("cart-item-detail", args=[item_id]), {"selected": False}, format="json"
        ).status_code
        == 200
    )
