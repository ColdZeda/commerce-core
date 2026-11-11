"""C 方案：Redis 预扣（Lua 原子）、提交、补偿与对账。只做实验，不接生产下单链路。"""

import redis
from django.conf import settings

from catalog.models import SKU

PREFIX = "lab:"
TTL_SECONDS = 24 * 3600

RESERVED = "RESERVED"
COMMITTED = "COMMITTED"
COMPENSATED = "COMPENSATED"

# 查记录 → 查库存 → 扣减 → 写记录在同一个脚本里，中间不会被别的命令插进来。
RESERVE_LUA = """
local state = redis.call('HGET', KEYS[2], 'state')
if state then
  return {'ALREADY_' .. state, redis.call('HGET', KEYS[2], 'stock_after')}
end
local stock = redis.call('GET', KEYS[1])
if not stock then
  return {'NO_STOCK', 0}
end
local qty = tonumber(ARGV[1])
if tonumber(stock) < qty then
  return {'INSUFFICIENT', tonumber(stock)}
end
local left = redis.call('DECRBY', KEYS[1], qty)
redis.call('HSET', KEYS[2], 'sku_id', ARGV[2], 'qty', ARGV[1], 'state', 'RESERVED', 'stock_after', left)
redis.call('EXPIRE', KEYS[2], tonumber(ARGV[3]))
redis.call('SADD', KEYS[3], ARGV[4])
redis.call('EXPIRE', KEYS[3], tonumber(ARGV[3]))
return {'RESERVED', left}
"""

COMMIT_LUA = """
local state = redis.call('HGET', KEYS[1], 'state')
if not state then
  return {'MISSING', 0}
end
if state ~= 'RESERVED' then
  return {'SKIPPED_' .. state, tonumber(redis.call('HGET', KEYS[1], 'stock_after'))}
end
redis.call('HSET', KEYS[1], 'state', 'COMMITTED')
return {'COMMITTED', tonumber(redis.call('HGET', KEYS[1], 'stock_after'))}
"""

COMPENSATE_LUA = """
local state = redis.call('HGET', KEYS[1], 'state')
if not state then
  return {'MISSING', 0}
end
if state ~= 'RESERVED' then
  return {'SKIPPED_' .. state, tonumber(redis.call('HGET', KEYS[1], 'stock_after'))}
end
local qty = tonumber(redis.call('HGET', KEYS[1], 'qty'))
local left = redis.call('INCRBY', KEYS[2], qty)
redis.call('HSET', KEYS[1], 'state', 'COMPENSATED', 'stock_after', left)
return {'COMPENSATED', left}
"""


def make_client() -> redis.Redis:
    return redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


def stock_key(sku_id: int) -> str:
    return f"{PREFIX}stock:{sku_id}"


def reservation_key(order_no: str) -> str:
    return f"{PREFIX}res:{order_no}"


def index_key(sku_id: int) -> str:
    return f"{PREFIX}index:{sku_id}"


def load_stock(sku_id: int, stock: int, client=None) -> None:
    (client or make_client()).set(stock_key(sku_id), stock)


def reserve(order_no: str, sku_id: int, qty: int, client=None) -> tuple[str, int]:
    """返回 (结果, 扣减后库存)；结果取 RESERVED / INSUFFICIENT / NO_STOCK / ALREADY_<状态>。"""
    client = client or make_client()
    status, stock_left = client.eval(
        RESERVE_LUA,
        3,
        stock_key(sku_id),
        reservation_key(order_no),
        index_key(sku_id),
        qty,
        sku_id,
        TTL_SECONDS,
        order_no,
    )
    return status, int(stock_left)


def commit(order_no: str, client=None) -> tuple[str, int]:
    """把 RESERVED 标记成 COMMITTED；重复调用返回 SKIPPED_<原状态>，不改库存。"""
    status, stock_left = (client or make_client()).eval(COMMIT_LUA, 1, reservation_key(order_no))
    return status, int(stock_left)


def compensate(order_no: str, sku_id: int, client=None) -> tuple[str, int]:
    """把 RESERVED 退回库存并标记 COMPENSATED；只有 RESERVED 会退，重复补偿不会二次加回。"""
    status, stock_left = (client or make_client()).eval(
        COMPENSATE_LUA, 2, reservation_key(order_no), stock_key(sku_id)
    )
    return status, int(stock_left)


def pending_qty(sku_id: int, client=None) -> int:
    client = client or make_client()
    total = 0
    for order_no in client.smembers(index_key(sku_id)):
        record = client.hgetall(reservation_key(order_no))
        if record.get("state") == RESERVED:
            total += int(record["qty"])
    return total


def reconcile(client=None) -> list[dict]:
    """按 sku 比较 redis 库存与 mysql 库存减在途预扣；只报告差异，不自动修。"""
    client = client or make_client()
    rows = []
    for sku in SKU.objects.order_by("pk"):
        raw = client.get(stock_key(sku.pk))
        if raw is None:
            continue
        pending = pending_qty(sku.pk, client=client)
        expected = sku.stock - pending
        actual = int(raw)
        if actual != expected:
            rows.append(
                {
                    "sku_id": sku.pk,
                    "redis_stock": actual,
                    "mysql_stock": sku.stock,
                    "reserved": pending,
                    "expected": expected,
                    "diff": actual - expected,
                }
            )
    return rows
