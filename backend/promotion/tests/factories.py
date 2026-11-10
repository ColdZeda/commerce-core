"""券的测试工厂。"""

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from promotion.models import Coupon


def make_coupon(
    name="满 100 减 20",
    total_qty=10,
    issued_qty=0,
    threshold="100.00",
    discount="20.00",
    days=7,
    is_active=True,
):
    now = timezone.now()
    return Coupon.objects.create(
        name=name,
        threshold_amount=Decimal(threshold),
        discount_amount=Decimal(discount),
        total_qty=total_qty,
        issued_qty=issued_qty,
        start_at=now - timedelta(days=1),
        end_at=now + timedelta(days=days),
        is_active=is_active,
    )
