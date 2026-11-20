from rest_framework import serializers

from .models import CartItem


class CartItemSerializer(serializers.ModelSerializer):
    sku_id = serializers.IntegerField(source="sku.id", read_only=True)
    sku_code = serializers.CharField(source="sku.sku_code", read_only=True)
    sku_title = serializers.CharField(source="sku.title", read_only=True)
    price = serializers.DecimalField(source="sku.price", max_digits=10, decimal_places=2, read_only=True)
    stock = serializers.IntegerField(source="sku.stock", read_only=True)
    product_id = serializers.IntegerField(source="sku.product.id", read_only=True)
    product_name = serializers.CharField(source="sku.product.name", read_only=True)
    cover = serializers.CharField(source="sku.product.cover", read_only=True)
    subtotal = serializers.SerializerMethodField()
    # 下架或库存不够时前端要能标出来，而不是等到结算才报错。
    available = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = [
            "id",
            "sku_id",
            "sku_code",
            "sku_title",
            "price",
            "stock",
            "product_id",
            "product_name",
            "cover",
            "qty",
            "subtotal",
            "available",
        ]

    def get_subtotal(self, obj):
        return str(obj.sku.price * obj.qty)

    def get_available(self, obj):
        return obj.sku.is_active and obj.sku.product.is_active and obj.qty <= obj.sku.stock


class AddItemSerializer(serializers.Serializer):
    sku_id = serializers.IntegerField(min_value=1)
    qty = serializers.IntegerField(min_value=1, max_value=999, default=1)


class UpdateQtySerializer(serializers.Serializer):
    qty = serializers.IntegerField(min_value=1, max_value=999)
