"""订单测试工厂：商品、SKU、用户券的最小组合。"""

from datetime import timedelta

from django.contrib.auth import get_user_model

from catalog.tests.factories import make_product, make_sku
from promotion.models import UserCoupon
from promotion.tests.factories import make_coupon
from trade.models import Order

User = get_user_model()


def make_buyer(username="buyer"):
    return User.objects.create_user(username=username, password="pw-buyer-123")


def make_sku_stock(price="30.00", stock=10, is_active=True):
    return make_sku(make_product(), price=price, stock=stock, is_active=is_active)


def make_user_coupon(user, threshold="50.00", discount="10.00"):
    coupon = make_coupon(threshold=threshold, discount=discount)
    return UserCoupon.objects.create(user=user, coupon=coupon)


def force_status(order: Order, status: int, **fields) -> Order:
    """把订单推到某个状态：只用于"已经是别的状态"这类前置条件。"""
    Order.objects.filter(pk=order.pk).update(status=status, **fields)
    order.refresh_from_db()
    return order


def expire_now(order: Order) -> Order:
    Order.objects.filter(pk=order.pk).update(expire_at=order.expire_at - timedelta(days=1))
    order.refresh_from_db()
    return order
