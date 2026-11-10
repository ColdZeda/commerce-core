"""并发领券：名额不能被并发冲爆，也不能因为冲突返回 500。"""

import threading

import pytest
from django.contrib.auth import get_user_model
from django.db import connection

from common.errors import BusinessError
from promotion.models import UserCoupon
from promotion.services import claim_coupon
from promotion.tests.factories import make_coupon

User = get_user_model()


@pytest.mark.concurrency
@pytest.mark.django_db(transaction=True)
def test_concurrent_claims_never_exceed_total_qty():
    coupon = make_coupon(total_qty=5)
    users = [User.objects.create_user(username=f"c{i}", password="pw-for-test") for i in range(12)]
    barrier = threading.Barrier(len(users))
    outcomes: list[str] = []
    lock = threading.Lock()

    def worker(user):
        barrier.wait()
        try:
            claim_coupon(user, coupon.pk)
            result = "ok"
        except BusinessError as exc:
            result = exc.get_codes()
        finally:
            connection.close()
        with lock:
            outcomes.append(result)

    threads = [threading.Thread(target=worker, args=(user,)) for user in users]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    coupon.refresh_from_db()
    assert outcomes.count("ok") == 5
    assert outcomes.count("COUPON_SOLD_OUT") == 7
    assert coupon.issued_qty == 5
    assert UserCoupon.objects.filter(coupon=coupon).count() == 5
