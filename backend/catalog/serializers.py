from rest_framework import serializers

from .models import SKU, Product


class ProductListSerializer(serializers.ModelSerializer):
    min_price = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True, read_only=True)

    class Meta:
        model = Product
        fields = ["id", "name", "subtitle", "cover_url", "min_price", "created_at"]


class SKUSerializer(serializers.ModelSerializer):
    class Meta:
        model = SKU
        fields = ["id", "sku_code", "title", "price", "stock"]


class ProductDetailSerializer(serializers.ModelSerializer):
    skus = serializers.SerializerMethodField()
    min_price = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ["id", "name", "subtitle", "description", "cover_url", "min_price", "skus", "created_at"]

    def get_skus(self, obj):
        return SKUSerializer(getattr(obj, "active_skus", []), many=True).data

    # 复用已 prefetch 的在售 SKU，避免为最低价再打一次聚合查询。
    def get_min_price(self, obj):
        prices = [sku.price for sku in getattr(obj, "active_skus", [])]
        return str(min(prices)) if prices else None
