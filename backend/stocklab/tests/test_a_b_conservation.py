"""A/B 在真实 MySQL 并发下的守恒：剩余库存 + 成功件数 == 初始库存。"""

import pytest

from catalog.models import SKU
from catalog.tests.factories import make_product, make_sku
from stocklab.deduct import NOT_ENOUGH, OK, RETRY_EXHAUSTED, deduct_locked, deduct_optimistic
from stocklab.tests.helpers import run_threads


@pytest.fixture
def stock_sku():
    def make(stock: int, price: str = "10.00"):
        return make_sku(make_product(), price=price, stock=stock)

    return make


@pytest.mark.concurrency
@pytest.mark.django_db(transaction=True)
def test_a_keeps_conservation_at_200_requests_over_50_threads(stock_sku):
    sku = stock_sku(100)

    results = run_threads(lambda _: deduct_locked(sku.pk, 1), 200, concurrency=50)

    ok = results.count(OK)
    left = SKU.objects.get(pk=sku.pk)
    assert ok == 100
    assert results.count(NOT_ENOUGH) == 100
    assert left.stock == 0
    assert left.stock + ok == 100


@pytest.mark.concurrency
@pytest.mark.django_db(transaction=True)
def test_b_keeps_conservation_at_200_requests_over_50_threads(stock_sku):
    sku = stock_sku(100)

    results = run_threads(lambda _: deduct_optimistic(sku.pk, 1), 200, concurrency=50)

    ok = results.count(OK)
    left = SKU.objects.get(pk=sku.pk)
    assert ok + results.count(NOT_ENOUGH) + results.count(RETRY_EXHAUSTED) == 200
    assert left.stock == 100 - ok
    assert left.stock >= 0
    assert ok <= 100


@pytest.mark.concurrency
@pytest.mark.django_db(transaction=True)
def test_hot_five_stock_never_goes_negative(stock_sku):
    sku = stock_sku(5)

    results = run_threads(lambda _: deduct_locked(sku.pk, 1), 120, concurrency=50)

    assert results.count(OK) == 5
    assert results.count(NOT_ENOUGH) == 115
    assert SKU.objects.get(pk=sku.pk).stock == 0


@pytest.mark.concurrency
@pytest.mark.django_db(transaction=True)
def test_both_paths_conserve_stock_on_the_same_scenario(stock_sku):
    a_sku = stock_sku(20)
    b_sku = stock_sku(20)

    a_results = run_threads(lambda _: deduct_locked(a_sku.pk, 1), 40, concurrency=20)
    b_results = run_threads(lambda _: deduct_optimistic(b_sku.pk, 1), 40, concurrency=20)

    a_ok = a_results.count(OK)
    b_ok = b_results.count(OK)
    a_left = SKU.objects.get(pk=a_sku.pk).stock
    b_left = SKU.objects.get(pk=b_sku.pk).stock

    assert a_ok == 20
    assert a_left == 0
    # B 的版本冲突次数有限，重试预算用完就放弃：卖不完但守恒仍然成立，这正是要记录的口径差异。
    assert b_left + b_ok == 20
    assert b_ok + b_results.count(NOT_ENOUGH) + b_results.count(RETRY_EXHAUSTED) == 40
