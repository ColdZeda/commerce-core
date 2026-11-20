"""注册：成功即登录、送新人券；撞名与弱口令都要停在字段级错误上。"""

import json

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from promotion.models import UserCoupon
from promotion.services import WELCOME_COUPON_NAME
from promotion.tests.factories import make_coupon

pytestmark = pytest.mark.django_db

User = get_user_model()
PASSWORD = "shop-pass-8848"


def register(client, **overrides):
    payload = {
        "username": "newbie",
        "password": PASSWORD,
        "password_confirm": PASSWORD,
    }
    payload.update(overrides)
    return client.post(reverse("auth-register"), data=json.dumps(payload), content_type="application/json")


def test_register_returns_tokens_and_logs_in(client):
    response = register(client)

    body = response.json()
    assert response.status_code == 201
    assert body["user"]["username"] == "newbie"
    assert body["user"]["is_staff"] is False
    assert body["access"] and body["refresh"]

    me = client.get(reverse("auth-me"), HTTP_AUTHORIZATION=f"Bearer {body['access']}")
    assert me.status_code == 200
    assert me.json()["username"] == "newbie"


def test_register_stores_hashed_password(client):
    register(client)

    user = User.objects.get(username="newbie")
    assert user.password != PASSWORD
    assert user.check_password(PASSWORD)


def test_register_grants_welcome_coupon(client):
    coupon = make_coupon(name=WELCOME_COUPON_NAME, total_qty=50)

    register(client)

    user = User.objects.get(username="newbie")
    assert UserCoupon.objects.filter(user=user, coupon=coupon).count() == 1
    coupon.refresh_from_db()
    assert coupon.issued_qty == 1


def test_register_without_seeded_coupon_still_succeeds(client):
    response = register(client)

    assert response.status_code == 201
    assert UserCoupon.objects.count() == 0


def test_register_with_duplicate_username_rejects(client):
    User.objects.create_user(username="newbie", password=PASSWORD)

    response = register(client)

    assert response.status_code == 400
    assert response.json()["detail"]["username"] == ["用户名已被占用"]


def test_register_rejects_case_insensitive_duplicate(client):
    User.objects.create_user(username="NewBie", password=PASSWORD)

    response = register(client)

    assert response.status_code == 400
    assert "username" in response.json()["detail"]


def test_register_rejects_mismatched_confirmation(client):
    response = register(client, password_confirm="another-pass-1")

    assert response.status_code == 400
    assert "password_confirm" in response.json()["detail"]


@pytest.mark.parametrize("weak", ["12345678", "password"])
def test_register_rejects_weak_password(client, weak):
    response = register(client, password=weak, password_confirm=weak)

    assert response.status_code == 400
    assert "password" in response.json()["detail"]
    assert not User.objects.filter(username="newbie").exists()


def test_register_strips_username_whitespace(client):
    response = register(client, username="  spaced  ")

    assert response.status_code == 201
    assert User.objects.filter(username="spaced").exists()


def test_register_does_not_grant_admin(client):
    register(client)

    assert User.objects.get(username="newbie").is_staff is False
