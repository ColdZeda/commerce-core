"""反例对照：先查状态再回补的关单写法会双回补，换成共享 service 只回补一次。"""

import threading

import pytest

from catalog.models import SKU
from stocklab.close_lab import close_unprotected
from stocklab.tests.helpers import run_threads
from trade.models import Order
from trade.services import close_order, create_order
from trade.tests.factories import expire_now, make_buyer, make_sku_stock


@pytest.mark.concurrency
@pytest.mark.django_db(transaction=True)
def test_unprotected_close_restocks_twice():
    buyer = make_buyer()
    sku = make_sku_stock(stock=10)
    order = expire_now(create_order(buyer, [{"sku_id": sku.pk, "qty": 2}])[0])
    barrier = threading.Barrier(2)

    results = run_threads(
        lambda _: close_unprotected(order.order_no, before_restock=barrier.wait), 2, concurrency=2
    )

    assert results.count(True) == 2
    # 两次都读到 PENDING、各回补 2 件：库存从 8 变成 12，比初始还多。
    assert SKU.objects.get(pk=sku.pk).stock == 12
    assert Order.objects.get(pk=order.pk).status == Order.Status.CLOSED


@pytest.mark.concurrency
@pytest.mark.django_db(transaction=True)
def test_shared_service_restocks_once_on_the_same_scenario():
    buyer = make_buyer()
    sku = make_sku_stock(stock=10)
    order = expire_now(create_order(buyer, [{"sku_id": sku.pk, "qty": 2}])[0])

    results = run_threads(lambda _: close_order(order.order_no) is not None, 2, concurrency=2)

    assert results.count(True) == 1
    assert SKU.objects.get(pk=sku.pk).stock == 10
