"""券只读：发放靠领券接口的条件更新，后台不能手工加量或改状态。"""

from django.contrib import admin

from .models import Coupon, UserCoupon


class ReadOnlyAdminMixin:
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Coupon)
class CouponAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("id", "name", "threshold_amount", "discount_amount", "issued_qty", "total_qty", "end_at")
    search_fields = ("name",)
    list_filter = ("is_active",)
    fields = (
        "name",
        "threshold_amount",
        "discount_amount",
        "total_qty",
        "issued_qty",
        "start_at",
        "end_at",
        "is_active",
        "created_at",
    )
    readonly_fields = fields


@admin.register(UserCoupon)
class UserCouponAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("id", "user", "coupon", "status", "received_at", "used_at")
    list_filter = ("status",)
    search_fields = ("user__username", "coupon__name")
    autocomplete_fields = ()
    fields = ("user", "coupon", "status", "received_at", "used_at", "created_at")
    readonly_fields = fields
