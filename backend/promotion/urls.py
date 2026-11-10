from django.urls import path

from .views import CouponClaimView, CouponListView, MyCouponListView

urlpatterns = [
    path("coupons", CouponListView.as_view(), name="coupon-list"),
    path("coupons/<int:pk>/claim", CouponClaimView.as_view(), name="coupon-claim"),
    path("me/coupons", MyCouponListView.as_view(), name="my-coupon-list"),
]
