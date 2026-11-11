"""规则表本身也是被测对象：迁移不能凭空出现，声明的副作用必须有实现。"""

from trade.models import Order
from trade.rules import RESTOCK, RETURN_COUPON, RULES, TRANSITIONS
from trade.services import EFFECTS


def test_cancel_restocks_and_returns_coupon():
    rule = RULES[(Order.Status.PENDING, Order.Status.CANCELLED)]

    assert set(rule.effects) == {RESTOCK, RETURN_COUPON}


def test_pay_has_no_stock_or_coupon_effects():
    # 支付是终态迁移，只写 paid_at；退款不在本项目范围内。
    rule = RULES[(Order.Status.PENDING, Order.Status.PAID)]

    assert rule.effects == ()


def test_only_pending_orders_can_move():
    # 终态不再有出边：取消/关闭之后不允许再迁移，否则库里会出现来回跳的订单。
    assert {rule.source for rule in TRANSITIONS} == {Order.Status.PENDING}


def test_every_declared_effect_is_implemented():
    declared = {effect for rule in TRANSITIONS for effect in rule.effects}

    assert declared <= set(EFFECTS)


def test_cancel_is_reachable_from_the_service_table():
    # 取消走的是同一张表，不是另写一套状态判断。
    assert (Order.Status.PENDING, Order.Status.CANCELLED) in RULES
