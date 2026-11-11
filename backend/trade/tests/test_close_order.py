"""关单：只关到期未支付、重复关单与重复任务只回补一次、取消与关单撞车不双补。"""

import threading

import pytest
from django.conf import settings
from django.db import connection
from django.utils import timezone

from catalog.models import SKU
from common.errors import BusinessError
from promotion.models import UserCoupon
from trade.models import Order
from trade.services import cancel_order, close_expired_orders, close_order, create_order
from trade.tasks import close_expired_orders as close_expired_task
from trade.tests.factories import expire_now, force_status, make_buyer, make_sku_stock, make_user_coupon

pytestmark = pytest.mark.django_db


@pytest.fixture
def buyer():
    return make_buyer()


@pytest.fixture
def sku():
    return make_sku_stock(stock=10)


def place(buyer, sku, qty=2, **kwargs):
    return create_order(buyer, [{"sku_id": sku.pk, "qty": qty}], **kwargs)[0]


def test_close_restocks_and_returns_coupon(buyer, sku):
    user_coupon = make_user_coupon(buyer, threshold="20.00", discount="5.00")
    order = place(buyer, sku, user_coupon_id=user_coupon.pk)
    expire_now(order)

    closed = close_order(order.order_no)

    assert closed.status == Order.Status.CLOSED
    assert closed.closed_at is not None
    assert SKU.objects.get(pk=sku.pk).stock == 10
    user_coupon.refresh_from_db()
    assert user_coupon.status == UserCoupon.Status.UNUSED


def test_close_twice_restocks_only_once(buyer, sku):
    order = place(buyer, sku)
    expire_now(order)

    first = close_order(order.order_no)
    second = close_order(order.order_no)

    assert first is not None
    assert second is None
    assert SKU.objects.get(pk=sku.pk).stock == 10


def test_only_expired_pending_orders_are_closed(buyer, sku):
    expired = expire_now(place(buyer, sku, qty=1))
    fresh = place(buyer, sku, qty=1)
    paid = force_status(expire_now(place(buyer, sku, qty=1)), Order.Status.PAID)

    result = close_expired_orders()

    # 扫表只挑 PENDING 且已到期的：已支付那单根本不在候选里。
    assert result == {"scanned": 1, "closed": 1, "skipped": 0}
    assert Order.objects.get(pk=expired.pk).status == Order.Status.CLOSED
    assert Order.objects.get(pk=fresh.pk).status == Order.Status.PENDING
    assert Order.objects.get(pk=paid.pk).status == Order.Status.PAID
    # 只有到期那单回了 1 件，已支付那单不参与回补。
    assert SKU.objects.get(pk=sku.pk).stock == 8


def test_batch_limit_and_repeat_task(buyer, sku):
    orders = [expire_now(place(buyer, sku, qty=1)) for _ in range(3)]

    first = close_expired_task(batch=2)
    second = close_expired_task(batch=2)
    third = close_expired_task(batch=2)

    assert first == {"scanned": 2, "closed": 2, "skipped": 0}
    assert second["closed"] == 1
    assert third == {"scanned": 0, "closed": 0, "skipped": 0}
    assert SKU.objects.get(pk=sku.pk).stock == 10
    assert all(Order.objects.get(pk=order.pk).status == Order.Status.CLOSED for order in orders)


def test_task_runs_through_celery_eagerly(buyer, sku):
    expire_now(place(buyer, sku, qty=1))

    result = close_expired_task.delay(batch=10)

    assert result.get() == {"scanned": 1, "closed": 1, "skipped": 0}


def test_beat_schedule_points_at_the_task():
    entry = settings.CELERY_BEAT_SCHEDULE["close-expired-orders"]

    assert entry["task"] == "trade.tasks.close_expired_orders"
    assert entry["schedule"] == 60.0
    assert close_expired_task.name == "trade.tasks.close_expired_orders"


def test_cancel_then_close_does_not_restock_again(buyer, sku):
    order = place(buyer, sku)
    expire_now(order)

    cancel_order(buyer, order.order_no)
    closed = close_order(order.order_no)

    assert closed is None
    assert Order.objects.get(pk=order.pk).status == Order.Status.CANCELLED
    assert SKU.objects.get(pk=sku.pk).stock == 10


def test_closed_order_cannot_be_cancelled(buyer, sku):
    order = expire_now(place(buyer, sku))
    close_order(order.order_no)

    with pytest.raises(BusinessError) as excinfo:
        cancel_order(buyer, order.order_no)

    assert excinfo.value.get_codes() == "ORDER_STATUS_INVALID"
    assert SKU.objects.get(pk=sku.pk).stock == 10


@pytest.mark.concurrency
@pytest.mark.django_db(transaction=True)
def test_concurrent_close_and_cancel_restock_once():
    buyer = make_buyer()
    sku = make_sku_stock(stock=10)
    order = create_order(buyer, [{"sku_id": sku.pk, "qty": 2}])[0]
    expire_now(order)

    barrier = threading.Barrier(6)
    outcomes: list[str] = []
    lock = threading.Lock()

    def worker(index):
        barrier.wait()
        try:
            if index % 2 == 0:
                result = "closed" if close_order(order.order_no) else "already-gone"
            else:
                cancel_order(buyer, order.order_no)
                result = "cancelled"
        except BusinessError as exc:
            result = exc.get_codes()
        connection.close()
        with lock:
            outcomes.append(result)

    threads = [threading.Thread(target=worker, args=(index,)) for index in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    final = Order.objects.get(pk=order.pk)
    refreshed = SKU.objects.get(pk=sku.pk)
    assert final.status in {Order.Status.CANCELLED, Order.Status.CLOSED}
    assert refreshed.stock == 10
    # 下单扣 1 次、回补 1 次；双回补会让版本号变 3。
    assert refreshed.version == 2
    assert len(outcomes) == 6
    assert timezone.now() > final.expire_at
