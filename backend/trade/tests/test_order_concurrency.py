"""并发下单与取消：同 token 只落一单、库存不超卖、取消只回补一次。"""

import threading

import pytest
from django.db import connection

from catalog.models import SKU
from common.errors import BusinessError
from promotion.models import UserCoupon
from trade.models import Order
from trade.services import cancel_order, create_order
from trade.tests.factories import make_buyer, make_sku_stock, make_user_coupon


def run_parallel(worker, count):
    barrier = threading.Barrier(count)
    results: list = []
    lock = threading.Lock()

    def wrapped(index):
        barrier.wait()
        try:
            outcome = worker(index)
        except BusinessError as exc:
            outcome = ("error", exc.get_codes())
        finally:
            connection.close()
        with lock:
            results.append(outcome)

    threads = [threading.Thread(target=wrapped, args=(index,)) for index in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    return results


@pytest.mark.concurrency
@pytest.mark.django_db(transaction=True)
def test_same_client_token_creates_exactly_one_order():
    buyer = make_buyer()
    sku = make_sku_stock(stock=10)

    def worker(_):
        order, replayed = create_order(buyer, [{"sku_id": sku.pk, "qty": 1}], client_token="dup-token")
        return "order", order.order_no, replayed

    results = run_parallel(worker, 8)

    assert len({number for _, number, _ in results}) == 1
    assert sum(1 for _, _, replayed in results if not replayed) == 1
    assert Order.objects.count() == 1
    assert SKU.objects.get(pk=sku.pk).stock == 9


@pytest.mark.concurrency
@pytest.mark.django_db(transaction=True)
def test_stock_is_never_oversold():
    buyer = make_buyer()
    sku = make_sku_stock(stock=5)

    def worker(_):
        order, _replayed = create_order(buyer, [{"sku_id": sku.pk, "qty": 1}])
        return "order", order.order_no

    results = run_parallel(worker, 12)

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
