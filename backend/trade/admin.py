"""订单只读：状态只能由接口的条件更新推进，后台不许绕过状态机改状态。"""

from django.contrib import admin

from .models import Order, OrderItem


class ReadOnlyAdminMixin:
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    fields = ("sku_code", "title", "unit_price", "qty", "subtotal")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("order_no", "user", "status", "pay_amount", "created_at", "paid_at")
    list_filter = ("status", "created_at")
    search_fields = ("order_no", "user__username")
    date_hierarchy = "created_at"
    inlines = [OrderItemInline]
    fields = (
        "order_no",
        "user",
        "status",
        "total_amount",
        "discount_amount",
        "pay_amount",
        "user_coupon",
        "expire_at",
        "paid_at",
        "closed_at",
        "cancel_reason",
        "client_token",
        "remark",
        "address_snapshot",
        "created_at",
    )
    readonly_fields = fields
