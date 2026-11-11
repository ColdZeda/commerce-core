"""C 方案实验：预扣、库存不足、并发、重复预扣、补偿、重复补偿、对账。全部对真实 Redis 跑。"""

import pytest

from catalog.models import SKU
from catalog.tests.factories import make_product, make_sku
from stocklab.redis_reserve import (
    COMPENSATED,
    RESERVED,
    commit,
    compensate,
    load_stock,
    reconcile,
    reserve,
    stock_key,
)
from stocklab.tests.helpers import run_threads

SKU_ID = 424242


def test_reserve_decrements_redis_stock(lab_redis):
    load_stock(SKU_ID, 5, client=lab_redis)

    status, left = reserve("OD-A", SKU_ID, 2, client=lab_redis)

    assert (status, left) == (RESERVED, 3)
    assert lab_redis.get(stock_key(SKU_ID)) == "3"


def test_reserve_rejects_more_than_stock(lab_redis):
    load_stock(SKU_ID, 1, client=lab_redis)

    status, left = reserve("OD-B", SKU_ID, 2, client=lab_redis)

    assert (status, left) == ("INSUFFICIENT", 1)
    assert lab_redis.get(stock_key(SKU_ID)) == "1"
    assert lab_redis.exists("lab:res:OD-B") == 0


def test_reserve_without_loaded_stock_is_reported(lab_redis):
    status, _ = reserve("OD-C", SKU_ID, 1, client=lab_redis)

    assert status == "NO_STOCK"


def test_duplicate_reserve_returns_stored_result_without_deducting_again(lab_redis):
    load_stock(SKU_ID, 5, client=lab_redis)
    first = reserve("OD-D", SKU_ID, 2, client=lab_redis)
    second = reserve("OD-D", SKU_ID, 2, client=lab_redis)

    assert first == (RESERVED, 3)
    assert second == ("ALREADY_RESERVED", 3)
    assert lab_redis.get(stock_key(SKU_ID)) == "3"


@pytest.mark.concurrency
def test_concurrent_reserve_never_oversells(lab_redis):
    load_stock(SKU_ID, 20, client=lab_redis)

    results = run_threads(
        lambda index: reserve(f"OD-CONC-{index}", SKU_ID, 1, client=lab_redis), 50, concurrency=20
    )

    statuses = [status for status, _ in results]
    assert statuses.count(RESERVED) == 20
    assert statuses.count("INSUFFICIENT") == 30
    assert lab_redis.get(stock_key(SKU_ID)) == "0"


def test_compensate_restores_stock_only_once(lab_redis):
    load_stock(SKU_ID, 5, client=lab_redis)
    reserve("OD-E", SKU_ID, 2, client=lab_redis)

    first = compensate("OD-E", SKU_ID, client=lab_redis)
    second = compensate("OD-E", SKU_ID, client=lab_redis)

    assert first == (COMPENSATED, 5)
    assert second == ("SKIPPED_COMPENSATED", 5)
    assert lab_redis.get(stock_key(SKU_ID)) == "5"


def _fail_to_persist():
    raise RuntimeError("模拟落库失败")


def test_db_failure_after_reserve_is_compensated(lab_redis):
    load_stock(SKU_ID, 5, client=lab_redis)
    reserve("OD-F", SKU_ID, 2, client=lab_redis)

    with pytest.raises(RuntimeError):
        _fail_to_persist()

    status, left = compensate("OD-F", SKU_ID, client=lab_redis)
    assert (status, left) == (COMPENSATED, 5)


def test_compensate_after_commit_does_nothing(lab_redis):
    load_stock(SKU_ID, 5, client=lab_redis)
    reserve("OD-G", SKU_ID, 2, client=lab_redis)
    commit("OD-G", client=lab_redis)

    status, left = compensate("OD-G", SKU_ID, client=lab_redis)

    assert status == "SKIPPED_COMMITTED"
    assert left == 3
    assert lab_redis.get(stock_key(SKU_ID)) == "3"


@pytest.mark.django_db
def test_reconcile_is_quiet_when_consistent(lab_redis):
    sku = make_sku(make_product(), stock=100)
    load_stock(sku.pk, 100, client=lab_redis)
    reserve("OD-H", sku.pk, 2, client=lab_redis)

    assert reconcile(client=lab_redis) == []

    commit("OD-H", client=lab_redis)
    SKU.objects.filter(pk=sku.pk).update(stock=98)
    assert reconcile(client=lab_redis) == []


@pytest.mark.django_db
def test_reconcile_reports_drift_without_fixing_it(lab_redis):
    sku = make_sku(make_product(), stock=100)
    load_stock(sku.pk, 100, client=lab_redis)
    lab_redis.incrby(stock_key(sku.pk), 3)

    rows = reconcile(client=lab_redis)

    assert len(rows) == 1
    assert rows[0]["diff"] == 3
    assert rows[0]["redis_stock"] == 103
    assert rows[0]["expected"] == 100
    assert lab_redis.get(stock_key(sku.pk)) == "103"


@pytest.mark.django_db
def test_reconcile_ignores_skus_the_c_path_never_loaded(lab_redis):
    make_sku(make_product(), stock=50)

    assert reconcile(client=lab_redis) == []
