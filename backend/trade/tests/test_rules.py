"""规则表本身也是被测对象：迁移不能凭空出现，声明的副作用必须有实现。"""

from trade.models import Order
from trade.rules import RESTOCK, RETURN_COUPON, RULES, TRANSITIONS
from trade.services import EFFECTS


def test_cancel_restocks_and_returns_coupon():
    rule = RULES[(Order.Status.PENDING, Order.Status.CANCELLED)]

    assert set(rule.effects) == {RESTOCK, RETURN_COUPON}


def test_refund_uses_the_same_effects_as_cancel():
    rule = RULES[(Order.Status.PAID, Order.Status.REFUNDED)]

    assert set(rule.effects) == {RESTOCK, RETURN_COUPON}


def test_pay_has_no_stock_or_coupon_effects():
    # 支付只写 paid_at；退券与回补属于退款那条规则。
    rule = RULES[(Order.Status.PENDING, Order.Status.PAID)]

    assert rule.effects == ()


def test_only_pending_and_paid_orders_have_outgoing_edges():
    assert {rule.source for rule in TRANSITIONS} == {Order.Status.PENDING, Order.Status.PAID}


def test_refunded_is_terminal():
    # 退款之后不允许再迁移，否则同一单可能被退第二次。
    assert not [rule for rule in TRANSITIONS if rule.source == Order.Status.REFUNDED]


def test_every_declared_effect_is_implemented():
    declared = {effect for rule in TRANSITIONS for effect in rule.effects}

    assert declared <= set(EFFECTS)


def test_cancel_is_reachable_from_the_service_table():
    # 取消走的是同一张表，不是另写一套状态判断。
    assert (Order.Status.PENDING, Order.Status.CANCELLED) in RULES
