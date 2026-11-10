"""券：可领列表、领取、我的券。列表匿名可见，领取需要登录。"""

from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from config.pagination import StandardPagination

from .models import Coupon, UserCoupon
from .serializers import CouponSerializer, UserCouponSerializer
from .services import claim_coupon

MY_COUPON_STATUS = {"unused", "used", "expired"}


class CouponListView(generics.ListAPIView):
    serializer_class = CouponSerializer
    pagination_class = StandardPagination
    permission_classes = [AllowAny]

    def get_queryset(self):
        now = timezone.now()
        return Coupon.objects.filter(is_active=True, start_at__lte=now, end_at__gte=now).order_by("-id")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        user = self.request.user
        # 登录用户多查一次已领集合，避免每条券单独查一次。
        context["claimed_ids"] = (
            set(UserCoupon.objects.filter(user=user).values_list("coupon_id", flat=True))
            if user.is_authenticated
            else set()
        )
        return context


class CouponClaimView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        user_coupon = claim_coupon(request.user, pk)
        return Response(UserCouponSerializer(user_coupon).data, status=status.HTTP_201_CREATED)


class MyCouponListView(generics.ListAPIView):
    serializer_class = UserCouponSerializer
    pagination_class = StandardPagination
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        status_param = self.request.query_params.get("status", "unused")
        if status_param not in MY_COUPON_STATUS:
            raise ValidationError({"status": [f"只支持 {', '.join(sorted(MY_COUPON_STATUS))}"]})

        now = timezone.now()
        queryset = UserCoupon.objects.select_related("coupon").filter(user=self.request.user)
        if status_param == "unused":
            return queryset.filter(status=UserCoupon.Status.UNUSED, coupon__end_at__gt=now).order_by("-id")
        if status_param == "used":
            return queryset.filter(status=UserCoupon.Status.USED).order_by("-id")
        return queryset.filter(status=UserCoupon.Status.UNUSED, coupon__end_at__lte=now).order_by("-id")
