"""手工压测：A/B 的单 SKU 扣减与完整下单、C 的 EVAL。默认 200 请求 / 50 并发 / 100 库存。

用法（backend 目录）：.venv\\Scripts\\python -m stocklab.bench
结果只有成功/失败、失败码、剩余库存与延迟，不产出 QPS 结论。
"""

import argparse
import os
import queue
import threading
import time
import uuid
from decimal import Decimal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.db import connection  # noqa: E402

from catalog.models import SKU, Product  # noqa: E402
from common.errors import BusinessError  # noqa: E402
from stocklab.deduct import OK, deduct_locked, deduct_optimistic  # noqa: E402
from stocklab.orders import create_order_optimistic  # noqa: E402
from stocklab.redis_reserve import load_stock, make_client, reserve, stock_key  # noqa: E402
from trade.models import Order  # noqa: E402
from trade.services import create_order  # noqa: E402


def run(worker, ops: int, concurrency: int) -> tuple[list, list, float]:
    tasks: queue.Queue[int] = queue.Queue()
    for index in range(ops):
        tasks.put(index)
    results: list = []
    latencies: list = []
    lock = threading.Lock()

    def body():
        try:
            while True:
                try:
                    index = tasks.get_nowait()
                except queue.Empty:
                    return
                started = time.perf_counter()
                outcome = worker(index)
                cost = (time.perf_counter() - started) * 1000
                with lock:
                    results.append(outcome)
                    latencies.append(cost)
        finally:
            connection.close()

    threads = [threading.Thread(target=body) for _ in range(min(concurrency, ops))]
    wall_start = time.perf_counter()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results, latencies, time.perf_counter() - wall_start


def percentile(values: list, ratio: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * ratio))]


def summarize(name: str, results: list, latencies: list, wall: float, stock_left, success_code=OK) -> dict:
    failures: dict[str, int] = {}
    success = 0
    for outcome in results:
        if outcome == success_code:
            success += 1
        else:
            failures[outcome] = failures.get(outcome, 0) + 1
    return {
        "场景": name,
        "成功": success,
        "失败": ", ".join(f"{code}×{count}" for code, count in sorted(failures.items())) or "—",
        "剩余库存": stock_left,
        "p50(ms)": round(percentile(latencies, 0.50), 1),
        "p95(ms)": round(percentile(latencies, 0.95), 1),
        "p99(ms)": round(percentile(latencies, 0.99), 1),
        "总计(s)": round(wall, 2),
    }


def make_sku(tag: str, stock: int) -> SKU:
    product = Product.objects.create(name=f"BENCH-{tag}")
    return SKU.objects.create(
        product=product,
        sku_code=f"BENCH-{tag}-{uuid.uuid4().hex[:8]}",
        title="bench",
        price=Decimal("10.00"),
        stock=stock,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ops", type=int, default=200)
    parser.add_argument("--concurrency", type=int, default=50)
    parser.add_argument("--stock", type=int, default=100)
    parser.add_argument("--keep", action="store_true", help="保留压测数据，便于手工检查")
    args = parser.parse_args()

    user = get_user_model().objects.get_or_create(username="bench")[0]
    redis_client = make_client()
    rows: list[dict] = []
    created: list[SKU] = []

    def finish(name, worker, stock_left, success_code=OK):
        results, latencies, wall = run(worker, args.ops, args.concurrency)
        rows.append(summarize(name, results, latencies, wall, stock_left(), success_code))
        print(f"{name} 完成，用时 {wall:.2f}s", flush=True)

    def place_order(index):
        try:
            create_order(user, [{"sku_id": sku_d.pk, "qty": 1}], client_token=f"bench-a-{index}")
            return OK
        except BusinessError as exc:
            return exc.get_codes()

    sku_a = make_sku("A", args.stock)
    created.append(sku_a)
    finish("A 单 SKU 扣减", lambda _: deduct_locked(sku_a.pk, 1), lambda: SKU.objects.get(pk=sku_a.pk).stock)

    sku_b = make_sku("B", args.stock)
    created.append(sku_b)
    finish(
        "B 单 SKU 扣减（3 次重试）",
        lambda _: deduct_optimistic(sku_b.pk, 1),
        lambda: SKU.objects.get(pk=sku_b.pk).stock,
    )

    sku_b2 = make_sku("B10", args.stock)
    created.append(sku_b2)
    finish(
        "B 单 SKU 扣减（10 次重试）",
        lambda _: deduct_optimistic(sku_b2.pk, 1, max_retries=10),
        lambda: SKU.objects.get(pk=sku_b2.pk).stock,
    )

    sku_c = make_sku("C", args.stock)
    created.append(sku_c)
    load_stock(sku_c.pk, args.stock, client=redis_client)
    finish(
        "C Redis EVAL 预扣",
        lambda index: reserve(f"BENCH-{sku_c.pk}-{index}", sku_c.pk, 1, client=redis_client)[0],
        lambda: redis_client.get(stock_key(sku_c.pk)),
        success_code="RESERVED",
    )

    sku_d = make_sku("D", args.stock)
    created.append(sku_d)
    finish("A 完整下单", place_order, lambda: SKU.objects.get(pk=sku_d.pk).stock)

    sku_e = make_sku("E", args.stock)
    created.append(sku_e)
    finish(
        "B 完整下单（单 SKU 无券）",
        lambda _: create_order_optimistic(user, sku_e.pk, 1)[0],
        lambda: SKU.objects.get(pk=sku_e.pk).stock,
    )

    print("| 场景 | 成功 | 失败 | 剩余库存 | p50(ms) | p95(ms) | p99(ms) | 总计(s) |")
    print("|---|---|---|---|---|---|---|---|")
    for row in rows:
        print("| " + " | ".join(str(row[key]) for key in row) + " |")

    if not args.keep:
        Order.objects.filter(user=user).delete()
        for sku in created:
            redis_client.delete(stock_key(sku.pk))
            product_id = sku.product_id
            sku.delete()
            Product.objects.filter(pk=product_id).delete()


if __name__ == "__main__":
    main()
