from django.contrib import admin
from django.utils.html import format_html

from .models import SKU, Product


class SKUInline(admin.TabularInline):
    model = SKU
    extra = 0
    fields = ("sku_code", "title", "price", "stock", "initial_stock", "is_active")
    readonly_fields = ("initial_stock",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("id", "cover_tag", "name", "category", "is_featured", "is_active", "created_at")
    list_display_links = ("id", "name")
    list_filter = ("category", "is_featured", "is_active")
    search_fields = ("name", "subtitle")
    list_editable = ("is_featured", "is_active")
    inlines = [SKUInline]

    @admin.display(description="封面")
    def cover_tag(self, obj):
        if not obj.cover:
            return "—"
        # 静态文件在容器里，后台页面走同一台 nginx，直接用站内路径即可。
        return format_html('<img src="{}" style="height:44px;border-radius:6px">', obj.cover)
