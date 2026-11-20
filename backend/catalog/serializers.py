from rest_framework import serializers

from .models import SKU, Product


class ProductListSerializer(serializers.ModelSerializer):
    min_price = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True, read_only=True)
    category_label = serializers.CharField(source="get_category_display", read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "subtitle",
            "cover",
            "category",
            "category_label",
            "is_featured",
            "min_price",
            "created_at",
        ]


class SKUSerializer(serializers.ModelSerializer):
    class Meta:
        model = SKU
        fields = ["id", "sku_code", "title", "price", "stock"]


class ProductDetailSerializer(serializers.ModelSerializer):
    skus = serializers.SerializerMethodField()
    min_price = serializers.SerializerMethodField()
    category_label = serializers.CharField(source="get_category_display", read_only=True)
    review_count = serializers.IntegerField(read_only=True, default=0)
    rating_average = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "subtitle",
            "description",
            "cover",
            "category",
            "category_label",
            "is_featured",
            "min_price",
            "review_count",
            "rating_average",
            "skus",
            "created_at",
        ]

    def get_skus(self, obj):
        return SKUSerializer(getattr(obj, "active_skus", []), many=True).data

    # 复用已 prefetch 的在售 SKU，避免为最低价再打一次聚合查询。
    def get_min_price(self, obj):
        prices = [sku.price for sku in getattr(obj, "active_skus", [])]
        return str(min(prices)) if prices else None

    def get_rating_average(self, obj):
        # annotate 出来的 Avg 是 Decimal；没有评价时是 None，前端据此显示"暂无评分"。
        average = getattr(obj, "rating_average", None)
        return round(float(average), 1) if average is not None else None
