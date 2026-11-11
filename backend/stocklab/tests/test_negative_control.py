"""反例对照：把保护拿掉，同一套守恒断言必须站不住；换回 A 又必须站得住。"""

import threading

import pytest

from catalog.models import SKU
from catalog.tests.factories import make_product, make_sku
from stocklab.deduct import OK, deduct_locked, deduct_unprotected
from stocklab.tests.helpers import run_threads


@pytest.mark.concurrency
@pytest.mark.django_db(transaction=True)
def test_unprotected_deduct_breaks_conservation():
    sku = make_sku(make_product(), stock=10)
    barrier = threading.Barrier(20)

    results = run_threads(
        lambda _: deduct_unprotected(sku.pk, 1, before_write=barrier.wait), 20, concurrency=20
    )

    ok = results.count(OK)
    left = SKU.objects.get(pk=sku.pk)
    # 先读后写的丢更新：20 个请求都读到"库存 10"、都扣成功，库存却只减了一次。
    assert ok > 10
    assert left.stock + ok != 10


@pytest.mark.concurrency
@pytest.mark.django_db(transaction=True)
def test_same_scenario_stays_conserved_on_the_locked_path():
    sku = make_sku(make_product(), stock=10)

    results = run_threads(lambda _: deduct_locked(sku.pk, 1), 20, concurrency=20)

    ok = results.count(OK)
    left = SKU.objects.get(pk=sku.pk)
    assert ok == 10
    assert left.stock + ok == 10
