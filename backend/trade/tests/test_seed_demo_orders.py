"""演示订单 seed：五种状态各一单、评价只评一次、跑完对账必须平。"""

from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

from audit.services import build_report
from catalog.models import SKU
from catalog.tests.factories import make_product, make_sku
from review.models import Review
from trade.models import Order

pytestmark = pytest.mark.django_db

User = get_user_model()


@pytest.fixture
def demo_user():
    return User.objects.create_user(username="demo", password="pw-demo-123")


@pytest.fixture
def catalog():
    product = make_product()
    return [make_sku(product, sku_code=f"DEMO-{index}", price="50.00", stock=20) for index in range(4)]


def test_seed_covers_every_status(demo_user, catalog):
    call_command("seed_demo_orders", stdout=StringIO())

    statuses = sorted(Order.objects.values_list("status", flat=True))
    assert statuses == sorted(Order.Status.values)
    assert Order.objects.get(order_no="ODDEMO0005").refunded_at is not None
    assert Order.objects.get(order_no="ODDEMO0003").cancel_reason.startswith("演示")
    assert Review.objects.count() == 2
    assert build_report()["summary"]["unbalanced"] == 0


def test_seed_is_idempotent_and_does_not_consume_stock_twice(demo_user, catalog):
    call_command("seed_demo_orders", stdout=StringIO())
    stock = {sku.pk: SKU.objects.get(pk=sku.pk).stock for sku in catalog}
    orders = Order.objects.count()

    call_command("seed_demo_orders", stdout=StringIO())

    assert Order.objects.count() == orders == 5
    assert Review.objects.count() == 2
    assert {sku.pk: SKU.objects.get(pk=sku.pk).stock for sku in catalog} == stock


def test_seed_needs_the_demo_account():
    with pytest.raises(CommandError):
        call_command("seed_demo_orders", stdout=StringIO())


def test_seed_needs_skus_first(demo_user):
    with pytest.raises(CommandError) as excinfo:
        call_command("seed_demo_orders", stdout=StringIO())

    assert "seed_demo" in str(excinfo.value)
