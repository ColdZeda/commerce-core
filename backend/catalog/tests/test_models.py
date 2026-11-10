"""数据库层约束：唯一键与 CHECK 必须在 MySQL 上真的拦住。"""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from catalog.tests.factories import make_product, make_sku
from trade.models import Order


@pytest.mark.django_db
def test_sku_code_must_be_unique():
    product = make_product()
    make_sku(product, sku_code="DUP-1")

    with pytest.raises(IntegrityError), transaction.atomic():
        make_sku(product, sku_code="DUP-1")


@pytest.mark.django_db
def test_stock_cannot_go_negative():
    product = make_product()

    with pytest.raises(IntegrityError), transaction.atomic():
        make_sku(product, sku_code="NEG-1", stock=-1)


@pytest.mark.django_db
def test_order_client_token_unique_per_user_but_null_is_repeatable():
    user = get_user_model().objects.create_user(username="buyer", password="pw-for-test")
    now = timezone.now()
    base = {
        "user": user,
        "total_amount": "10.00",
        "pay_amount": "10.00",
        "expire_at": now + timedelta(minutes=15),
    }

    Order.objects.create(order_no="NO-NULL-1", **base)
    Order.objects.create(order_no="NO-NULL-2", **base)

    Order.objects.create(order_no="NO-TOKEN-1", client_token="tok-1", **base)
    with pytest.raises(IntegrityError), transaction.atomic():
        Order.objects.create(order_no="NO-TOKEN-2", client_token="tok-1", **base)
