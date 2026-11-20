"""地址接口：默认地址唯一、越权 404、删掉默认后有人顶上。"""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from address.models import Address
from trade.models import Order
from trade.tests.factories import make_buyer, make_sku_stock

pytestmark = pytest.mark.django_db

VALID = {
    "receiver": "张三",
    "phone": "13800138000",
    "region": "广东省 深圳市 南山区",
    "detail": "科技园 1 号 A 座 1801",
}


@pytest.fixture
def buyer():
    return make_buyer()


@pytest.fixture
def auth_client(buyer):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(buyer)}")
    return client


def create(client, **overrides):
    return client.post(reverse("address-list"), {**VALID, **overrides}, format="json")


def test_address_requires_login(client):
    assert client.get(reverse("address-list")).status_code == 401


def test_first_address_becomes_default(auth_client, buyer):
    response = create(auth_client)

    assert response.status_code == 201
    assert response.json()["is_default"] is True
    addresses = auth_client.get(reverse("address-list")).json()["items"]
    assert len(addresses) == 1
    assert addresses[0]["receiver"] == "张三"


def test_second_address_is_not_default_by_default(auth_client):
    create(auth_client)
    second = create(auth_client, receiver="李四").json()

    assert second["is_default"] is False
    assert Address.objects.filter(is_default=True).count() == 1


def test_setting_default_unsets_the_previous_one(auth_client):
    create(auth_client)
    second = create(auth_client, receiver="李四").json()

    response = auth_client.patch(
        reverse("address-detail", args=[second["id"]]), {"is_default": True}, format="json"
    )

    assert response.status_code == 200
    assert response.json()["is_default"] is True
    assert Address.objects.filter(is_default=True).count() == 1
    assert Address.objects.get(receiver="张三").is_default is False


def test_patch_updates_fields(auth_client):
    address = create(auth_client).json()

    response = auth_client.patch(
        reverse("address-detail", args=[address["id"]]),
        {"receiver": "王五", "detail": "新地址 2 号"},
        format="json",
    )

    assert response.json()["receiver"] == "王五"
    assert response.json()["detail"] == "新地址 2 号"
    assert response.json()["region"] == VALID["region"]


def test_delete_default_promotes_another(auth_client):
    first = create(auth_client).json()
    second = create(auth_client, receiver="李四").json()

    assert auth_client.delete(reverse("address-detail", args=[first["id"]])).status_code == 204

    remaining = Address.objects.get(pk=second["id"])
    assert remaining.is_default is True


@pytest.mark.parametrize("phone", ["abc", "123", "1234567890123456"])
def test_phone_must_be_digits_in_range(auth_client, phone):
    response = create(auth_client, phone=phone)

    assert response.status_code == 400
    assert "phone" in response.json()["detail"]


def test_phone_accepts_separators(auth_client):
    response = create(auth_client, phone="138-0013-8000")

    assert response.status_code == 201
    assert response.json()["phone"] == "13800138000"


def test_other_users_address_is_404(auth_client, client, buyer):
    address = create(auth_client).json()
    stranger = make_buyer(username="addr-stranger")
    stranger_client = APIClient()
    stranger_client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(stranger)}")

    assert stranger_client.get(reverse("address-list")).json()["items"] == []
    assert (
        stranger_client.patch(
            reverse("address-detail", args=[address["id"]]), {"receiver": "X"}, format="json"
        ).status_code
        == 404
    )
    assert stranger_client.delete(reverse("address-detail", args=[address["id"]])).status_code == 404


def test_order_snapshots_the_address(auth_client):
    address = create(auth_client).json()
    sku = make_sku_stock(price="50.00", stock=10)

    response = auth_client.post(
        reverse("order-list"),
        {"items": [{"sku_id": sku.pk, "qty": 1}], "address_id": address["id"]},
        format="json",
    )

    assert response.status_code == 201
    assert response.json()["address_snapshot"] == {
        "receiver": VALID["receiver"],
        "phone": VALID["phone"],
        "region": VALID["region"],
        "detail": VALID["detail"],
    }


def test_snapshot_survives_address_edit_and_delete(auth_client):
    address = create(auth_client).json()
    sku = make_sku_stock(price="50.00", stock=10)
    order_no = auth_client.post(
        reverse("order-list"),
        {"items": [{"sku_id": sku.pk, "qty": 1}], "address_id": address["id"]},
        format="json",
    ).json()["order_no"]

    auth_client.patch(reverse("address-detail", args=[address["id"]]), {"receiver": "改名了"}, format="json")
    auth_client.delete(reverse("address-detail", args=[address["id"]]))

    detail = auth_client.get(reverse("order-detail", args=[order_no])).json()
    assert detail["address_snapshot"]["receiver"] == "张三"


def test_unknown_address_id_is_rejected(auth_client):
    sku = make_sku_stock(price="50.00", stock=10)

    response = auth_client.post(
        reverse("order-list"),
        {"items": [{"sku_id": sku.pk, "qty": 1}], "address_id": 999_999},
        format="json",
    )

    assert response.status_code == 400
    assert Order.objects.count() == 0


def test_order_without_address_still_works(auth_client):
    sku = make_sku_stock(price="50.00", stock=10)

    response = auth_client.post(
        reverse("order-list"), {"items": [{"sku_id": sku.pk, "qty": 1}]}, format="json"
    )

    assert response.status_code == 201
    assert response.json()["address_snapshot"] is None
