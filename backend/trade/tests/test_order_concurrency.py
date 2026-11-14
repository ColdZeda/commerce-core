"""并发下单与取消：同 token 只落一单、库存不超卖、取消只回补一次。"""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from django.db import connection

from catalog.models import SKU
from common.errors import BusinessError
from promotion.models import UserCoupon
from trade import services
from trade.models import Order
from trade.services import cancel_order, create_order
from trade.tests.factories import make_buyer, make_sku_stock, make_user_coupon


def run_parallel(worker, count):
    """跑 count 个线程并收齐全部结果；意外异常在主线程重放，不能只在线程里消失。"""
    barrier = threading.Barrier(count)

    def wrapped(index):
        barrier.wait(timeout=30)
        try:
            return worker(index)
        except BusinessError as exc:
            return ("error", exc.get_codes())
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=count) as executor:
        futures = [executor.submit(wrapped, index) for index in range(count)]
        return [future.result(timeout=30) for future in futures]


@pytest.mark.concurrency
@pytest.mark.django_db(transaction=True)
def test_same_client_token_creates_exactly_one_order():
    buyer = make_buyer()
    sku = make_sku_stock(stock=10)

    def worker(_):
        order, replayed = create_order(buyer, [{"sku_id": sku.pk, "qty": 1}], client_token="dup-token")
        return "order", order.order_no, replayed

    results = run_parallel(worker, 8)

    assert len(results) == 8
    assert len({number for _, number, _ in results}) == 1
    assert sum(1 for _, _, replayed in results if replayed) == 7
    assert Order.objects.count() == 1
    assert SKU.objects.get(pk=sku.pk).stock == 9


@pytest.mark.concurrency
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("with_coupon", [False, True], ids=["last-item", "used-coupon"])
def test_same_token_replays_even_when_loser_fails_resource_check(monkeypatch, with_coupon):
    """赢家耗尽最后一件库存或用掉券后，输家的校验会先失败：仍须返回原单，不能回 409。"""
    buyer = make_buyer()
    sku = make_sku_stock(stock=10 if with_coupon else 1)
    coupon = make_user_coupon(buyer, threshold="10.00", discount="5.00") if with_coupon else None
    barrier = threading.Barrier(2)
    real_lock_skus = services._lock_skus

    def lock_after_both_passed_token_lookup(items):
        barrier.wait(timeout=30)
        return real_lock_skus(items)

    monkeypatch.setattr(services, "_lock_skus", lock_after_both_passed_token_lookup)

    def worker(_):
        order, replayed = create_order(
            buyer,
            [{"sku_id": sku.pk, "qty": 1}],
            user_coupon_id=coupon.pk if coupon else None,
            client_token="same-request",
        )
        return "order", order.order_no, replayed

    results = run_parallel(worker, 2)

    assert len(results) == 2, results
    assert all(kind == "order" for kind, *_ in results), results
    assert len({number for _, number, _ in results}) == 1
    assert sorted(replayed for _, _, replayed in results) == [False, True]
    assert Order.objects.count() == 1
    assert SKU.objects.get(pk=sku.pk).stock == (9 if with_coupon else 0)


@pytest.mark.concurrency
@pytest.mark.django_db(transaction=True)
def test_run_parallel_surfaces_unexpected_worker_errors():
    def worker(_):
        raise RuntimeError("worker crashed")

    with pytest.raises(RuntimeError):
        run_parallel(worker, 4)


@pytest.mark.concurrency
@pytest.mark.django_db(transaction=True)
def test_stock_is_never_oversold():
    buyer = make_buyer()
    sku = make_sku_stock(stock=5)

    def worker(_):
        order, _replayed = create_order(buyer, [{"sku_id": sku.pk, "qty": 1}])
        return "order", order.order_no

    results = run_parallel(worker, 12)

    assert len(results) == 12
    assert sum(1 for kind, _ in results if kind == "order") == 5
    assert [payload for kind, payload in results if kind == "error"].count("STOCK_NOT_ENOUGH") == 7
    refreshed = SKU.objects.get(pk=sku.pk)
    assert refreshed.stock == 0
    assert refreshed.version == 5
    assert Order.objects.count() == 5


@pytest.mark.concurrency
@pytest.mark.django_db(transaction=True)
def test_concurrent_cancel_restocks_only_once():
    buyer = make_buyer()
    sku = make_sku_stock(stock=10)
    user_coupon = make_user_coupon(buyer, threshold="20.00", discount="5.00")
    order, _ = create_order(buyer, [{"sku_id": sku.pk, "qty": 2}], user_coupon_id=user_coupon.pk)

    def worker(_):
        return "order", cancel_order(buyer, order.order_no).status

    results = run_parallel(worker, 6)

    assert results == [("order", Order.Status.CANCELLED)] * 6
    assert SKU.objects.get(pk=sku.pk).stock == 10
    user_coupon.refresh_from_db()
    assert user_coupon.status == UserCoupon.Status.UNUSED
