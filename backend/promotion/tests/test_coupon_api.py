"""券接口契约：可领范围、重复领取、售罄、我的券筛选。"""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from promotion.models import Coupon, UserCoupon
from promotion.tests.factories import make_coupon

pytestmark = pytest.mark.django_db

User = get_user_model()


@pytest.fixture
def user():
    return User.objects.create_user(username="buyer", password="pw-buyer-123")


@pytest.fixture
def auth_client(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return client


def test_list_only_returns_claimable_coupons(client):
    make_coupon(name="可领")
    make_coupon(name="已下架", is_active=False)
    make_coupon(name="还没开始")
    make_coupon(name="已结束")
    Coupon.objects.filter(name="还没开始").update(start_at=timezone.now() + timedelta(days=1))
    Coupon.objects.filter(name="已结束").update(end_at=timezone.now() - timedelta(days=1))

    payload = client.get(reverse("coupon-list")).json()

    assert payload["count"] == 1
    assert payload["results"][0]["name"] == "可领"
    assert payload["results"][0]["claimed"] is False
    assert payload["results"][0]["remaining"] == 10


def test_list_marks_claimed_for_logged_in_user(auth_client, user):
    coupon = make_coupon(name="领过的")
    make_coupon(name="没领过的")
    UserCoupon.objects.create(user=user, coupon=coupon)

    payload = auth_client.get(reverse("coupon-list")).json()

    flags = {item["name"]: item["claimed"] for item in payload["results"]}
    assert flags == {"领过的": True, "没领过的": False}


def test_claim_creates_user_coupon_and_counts_quota(auth_client, user):
    coupon = make_coupon(total_qty=3)

    response = auth_client.post(reverse("coupon-claim", args=[coupon.pk]))

    assert response.status_code == 201
    assert response.json()["coupon"]["id"] == coupon.pk
    assert UserCoupon.objects.filter(user=user, coupon=coupon).count() == 1
    coupon.refresh_from_db()
    assert coupon.issued_qty == 1


def test_claim_twice_returns_already_claimed_without_burning_quota(auth_client, user):
    coupon = make_coupon(total_qty=3)
    auth_client.post(reverse("coupon-claim", args=[coupon.pk]))

    response = auth_client.post(reverse("coupon-claim", args=[coupon.pk]))

    assert response.status_code == 409
    assert response.json()["code"] == "COUPON_ALREADY_CLAIMED"
    coupon.refresh_from_db()
    assert coupon.issued_qty == 1


def test_claim_sold_out_returns_business_code(auth_client):
    coupon = make_coupon(total_qty=1, issued_qty=1)

    response = auth_client.post(reverse("coupon-claim", args=[coupon.pk]))

    assert response.status_code == 409
    assert response.json()["code"] == "COUPON_SOLD_OUT"


def test_claim_expired_coupon_returns_not_usable(auth_client):
    coupon = make_coupon()
    Coupon.objects.filter(pk=coupon.pk).update(end_at=timezone.now() - timedelta(minutes=1))

    response = auth_client.post(reverse("coupon-claim", args=[coupon.pk]))

    assert response.status_code == 409
    assert response.json()["code"] == "COUPON_NOT_USABLE"


def test_claim_requires_login(client):
    coupon = make_coupon()

    response = client.post(reverse("coupon-claim", args=[coupon.pk]))

    assert response.status_code == 401
    assert response.json()["code"] == "TOKEN_INVALID"


def test_my_coupons_filters_by_status(auth_client, user):
    usable = make_coupon(name="可用")
    expired = make_coupon(name="过期")
    Coupon.objects.filter(pk=expired.pk).update(end_at=timezone.now() - timedelta(minutes=1))
    used = make_coupon(name="已用")

    UserCoupon.objects.create(user=user, coupon=usable)
    UserCoupon.objects.create(user=user, coupon=expired)
    UserCoupon.objects.create(user=user, coupon=used, status=UserCoupon.Status.USED, used_at=timezone.now())

    def names(status):
        payload = auth_client.get(reverse("my-coupon-list"), {"status": status}).json()
        return [item["coupon"]["name"] for item in payload["results"]]

    assert names("unused") == ["可用"]
    assert names("used") == ["已用"]
    assert names("expired") == ["过期"]

    bad = auth_client.get(reverse("my-coupon-list"), {"status": "whatever"})
    assert bad.status_code == 400
    assert bad.json()["code"] == "VALIDATION_ERROR"
