from django.contrib import admin

from .models import SKU, Product


class SKUInline(admin.TabularInline):
    model = SKU
    extra = 0
    fields = ("sku_code", "title", "price", "stock", "is_active")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "subtitle")
    inlines = [SKUInline]
