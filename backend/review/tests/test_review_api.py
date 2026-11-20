"""评论：只有已支付订单的明细能评，一条明细一次，商品页免登录可读。"""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from review.models import Review
from trade.models import Order
from trade.services import create_order
from trade.tests.factories import force_status, make_address, make_buyer, make_sku_stock

pytestmark = pytest.mark.django_db


@pytest.fixture
def buyer():
    return make_buyer()


@pytest.fixture
def auth_client(buyer):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(buyer)}")
    return client


def paid_order(buyer, skus, **kwargs):
    """造一张已支付订单：先按正常链路下单，再把状态推过去。"""
    address = make_address(buyer)
    order = create_order(
        buyer,
        [{"sku_id": sku.pk, "qty": 1} for sku in skus],
        address=address,
        **kwargs,
    )[0]
    return force_status(order, Order.Status.PAID)


def submit(client, order_no, entries):
    return client.post(reverse("order-review", args=[order_no]), {"reviews": entries}, format="json")


def test_review_requires_login(client):
    response = client.post(reverse("order-review", args=["OD20260101000000000001"]), {}, format="json")

    assert response.status_code == 401


def test_pending_order_cannot_be_reviewed(auth_client, buyer):
    sku = make_sku_stock()
    order = create_order(buyer, [{"sku_id": sku.pk, "qty": 1}], address=make_address(buyer))[0]
    item = order.items.get()

    response = submit(auth_client, order.order_no, [{"order_item_id": item.pk, "rating": 5}])

    assert response.status_code == 409
    assert response.json()["code"] == "REVIEW_ORDER_NOT_PAID"
    assert Review.objects.count() == 0


def test_other_users_order_is_404(auth_client, buyer):
    stranger = make_buyer(username="review-stranger")
    order = paid_order(stranger, [make_sku_stock()])
    item = order.items.get()

    response = submit(auth_client, order.order_no, [{"order_item_id": item.pk, "rating": 5}])

    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_item_not_in_order_is_404(auth_client, buyer):
    order = paid_order(buyer, [make_sku_stock()])
    other_order = paid_order(buyer, [make_sku_stock()])
    foreign_item = other_order.items.get()

    response = submit(auth_client, order.order_no, [{"order_item_id": foreign_item.pk, "rating": 4}])

    assert response.status_code == 404
    assert Review.objects.count() == 0


def test_review_is_created_and_linked_to_product(auth_client, buyer):
    sku = make_sku_stock()
    order = paid_order(buyer, [sku])
    item = order.items.get()

    response = submit(
        auth_client, order.order_no, [{"order_item_id": item.pk, "rating": 5, "content": "手感不错"}]
    )

    assert response.status_code == 201
    assert response.json()["created"] == 1
    review = Review.objects.get()
    assert review.rating == 5
    assert review.content == "手感不错"
    assert review.product_id == sku.product_id
    assert review.order_item_id == item.pk


def test_review_twice_is_rejected(auth_client, buyer):
    order = paid_order(buyer, [make_sku_stock()])
    item = order.items.get()
    submit(auth_client, order.order_no, [{"order_item_id": item.pk, "rating": 5}])

    again = submit(auth_client, order.order_no, [{"order_item_id": item.pk, "rating": 3}])

    assert again.status_code == 409
    assert again.json()["code"] == "REVIEW_ALREADY_EXISTS"
    assert Review.objects.count() == 1


def test_duplicate_item_in_one_request_is_rejected(auth_client, buyer):
    order = paid_order(buyer, [make_sku_stock()])
    item = order.items.get()

    response = submit(
        auth_client,
        order.order_no,
        [{"order_item_id": item.pk, "rating": 5}, {"order_item_id": item.pk, "rating": 4}],
    )

    assert response.status_code == 400
    assert Review.objects.count() == 0


@pytest.mark.parametrize("rating", [0, 6])
def test_rating_must_be_between_one_and_five(auth_client, buyer, rating):
    order = paid_order(buyer, [make_sku_stock()])
    item = order.items.get()

    response = submit(auth_client, order.order_no, [{"order_item_id": item.pk, "rating": rating}])

    assert response.status_code == 400


def test_batch_is_atomic(auth_client, buyer):
    first, second = make_sku_stock(), make_sku_stock()
    order = paid_order(buyer, [first, second])
    items = list(order.items.order_by("id"))
    other_item = paid_order(buyer, [make_sku_stock()]).items.get()

    response = submit(
        auth_client,
        order.order_no,
        [{"order_item_id": items[0].pk, "rating": 5}, {"order_item_id": other_item.pk, "rating": 5}],
    )

    assert response.status_code == 404
    # 一条坏掉整批都不落库，不留"评了一半"。
    assert Review.objects.count() == 0


def test_empty_reviews_is_rejected(auth_client, buyer):
    order = paid_order(buyer, [make_sku_stock()])

    response = submit(auth_client, order.order_no, [])

    assert response.status_code == 400


def test_product_reviews_are_public_and_carry_summary(client, buyer):
    sku = make_sku_stock()
    order = paid_order(buyer, [sku])
    item = order.items.get()
    Review.objects.create(user=buyer, order_item=item, product_id=sku.product_id, rating=4, content="还行")

    response = client.get(reverse("product-reviews", args=[sku.product_id]))

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["summary"] == {"count": 1, "average": 4.0}
    assert payload["results"][0]["content"] == "还行"


def test_product_reviews_mask_username(client, buyer):
    sku = make_sku_stock()
    order = paid_order(buyer, [sku])
    item = order.items.get()
    Review.objects.create(user=buyer, order_item=item, product_id=sku.product_id, rating=5)

    payload = client.get(reverse("product-reviews", args=[sku.product_id])).json()

    assert payload["results"][0]["username"] == "b***"
    assert "buyer" not in payload["results"][0]["username"]


def test_product_reviews_404_for_missing_product(client):
    response = client.get(reverse("product-reviews", args=[999_999]))

    assert response.status_code == 404


def test_product_detail_carries_rating(client, buyer):
    sku = make_sku_stock()
    order = paid_order(buyer, [sku])
    item = order.items.get()
    Review.objects.create(user=buyer, order_item=item, product_id=sku.product_id, rating=5)

    payload = client.get(reverse("product-detail", args=[sku.product_id])).json()

    assert payload["review_count"] == 1
    assert payload["rating_average"] == 5.0


def test_product_detail_without_reviews_has_null_average(client):
    sku = make_sku_stock()

    payload = client.get(reverse("product-detail", args=[sku.product_id])).json()

    assert payload["review_count"] == 0
    assert payload["rating_average"] is None
