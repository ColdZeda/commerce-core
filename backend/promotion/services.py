"""领券：条件增加 issued_qty 是总量闸门，唯一索引是同一用户的第二道闸。"""

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone
from rest_framework import status

from common.errors import BusinessError

from .models import Coupon, UserCoupon


def claim_coupon(user, coupon_id: int) -> UserCoupon:
    """领取一张券；成功返回 UserCoupon。

    抛 BusinessError：COUPON_NOT_USABLE / COUPON_ALREADY_CLAIMED / COUPON_SOLD_OUT。
    """
    now = timezone.now()
    with transaction.atomic():
        coupon = Coupon.objects.filter(pk=coupon_id).first()
        if coupon is None or not coupon.is_active or not (coupon.start_at <= now <= coupon.end_at):
            raise BusinessError("COUPON_NOT_USABLE", "优惠券不可领取", status.HTTP_409_CONFLICT)

        if UserCoupon.objects.filter(user=user, coupon=coupon).exists():
            raise BusinessError("COUPON_ALREADY_CLAIMED", "已经领过这张券", status.HTTP_409_CONFLICT)

        # 条件更新保证 issued_qty 不会越过 total_qty，rowcount 就是"抢到名额"的凭据。
        granted = Coupon.objects.filter(pk=coupon.pk, issued_qty__lt=F("total_qty")).update(
            issued_qty=F("issued_qty") + 1
        )
        if not granted:
            raise BusinessError("COUPON_SOLD_OUT", "优惠券已领完", status.HTTP_409_CONFLICT)

        try:
            with transaction.atomic():
                return UserCoupon.objects.create(user=user, coupon=coupon)
        except IntegrityError:
            # 并发下同一个人同时领两次：唯一索引兜住，并把上面加的名额回滚掉。
            raise BusinessError(
                "COUPON_ALREADY_CLAIMED", "已经领过这张券", status.HTTP_409_CONFLICT
            ) from None
