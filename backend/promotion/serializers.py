from django.utils import timezone
from rest_framework import serializers

from .models import Coupon, UserCoupon


class CouponSerializer(serializers.ModelSerializer):
    remaining = serializers.SerializerMethodField()
    claimed = serializers.SerializerMethodField()

    class Meta:
        model = Coupon
        fields = [
            "id",
            "name",
            "threshold_amount",
            "discount_amount",
            "total_qty",
            "issued_qty",
            "remaining",
            "start_at",
            "end_at",
            "claimed",
        ]

    def get_remaining(self, obj) -> int:
        return max(obj.total_qty - obj.issued_qty, 0)

    def get_claimed(self, obj) -> bool:
        return obj.pk in self.context.get("claimed_ids", set())


class UserCouponSerializer(serializers.ModelSerializer):
    coupon = CouponSerializer(read_only=True)
    usable = serializers.SerializerMethodField()

    class Meta:
        model = UserCoupon
        fields = ["id", "status", "received_at", "used_at", "usable", "coupon"]

    def get_usable(self, obj) -> bool:
        return obj.status == UserCoupon.Status.UNUSED and obj.coupon.end_at > timezone.now()
