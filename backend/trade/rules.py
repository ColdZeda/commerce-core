"""订单状态迁移规则：允许哪些迁移、各带哪些副作用，都写成数据而不是散落的 if。

加一条迁移只改这张表；执行方式（条件更新 + 副作用）对所有迁移是同一套。
"""

from dataclasses import dataclass

from .models import Order

RESTOCK = "restock"
RETURN_COUPON = "return_coupon"


@dataclass(frozen=True)
class Transition:
    source: int
    target: int
    # 名字由 services.EFFECTS 落实；这里只声明"必须发生什么"，不声明怎么做。
    effects: tuple[str, ...]


TRANSITIONS = (
    # 用户取消与超时关单共用同一条副作用：回补库存、退券都必须在同一事务里。
    Transition(
        source=Order.Status.PENDING,
        target=Order.Status.CANCELLED,
        effects=(RESTOCK, RETURN_COUPON),
    ),
    Transition(
        source=Order.Status.PENDING,
        target=Order.Status.CLOSED,
        effects=(RESTOCK, RETURN_COUPON),
    ),
    # 支付只写 paid_at 这一列，没有跨表副作用。
    Transition(
        source=Order.Status.PENDING,
        target=Order.Status.PAID,
        effects=(),
    ),
    # 整单退款：钱退回去，货和券也得回到下单前，所以复用取消/关单那两条副作用。
    Transition(
        source=Order.Status.PAID,
        target=Order.Status.REFUNDED,
        effects=(RESTOCK, RETURN_COUPON),
    ),
)

RULES = {(rule.source, rule.target): rule for rule in TRANSITIONS}
