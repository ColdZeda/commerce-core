from rest_framework import serializers

from .models import Order, OrderItem

MAX_LINES = 20
MAX_QTY_PER_LINE = 999


class OrderLineInputSerializer(serializers.Serializer):
    sku_id = serializers.IntegerField(min_value=1)
    qty = serializers.IntegerField(min_value=1, max_value=MAX_QTY_PER_LINE)


class OrderCreateSerializer(serializers.Serializer):
    items = OrderLineInputSerializer(many=True, allow_empty=False)
    user_coupon_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    client_token = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    remark = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")

    def validate_items(self, items):
        if len(items) > MAX_LINES:
            raise serializers.ValidationError(f"一单最多 {MAX_LINES} 个 SKU")
        # 合并数量会让快照里看不出"提交了几行"，契约上直接拒绝更清楚。
        if len({item["sku_id"] for item in items}) != len(items):
            raise serializers.ValidationError("同一 SKU 只能提交一次")
        return items


class OrderCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class OrderPaySerializer(serializers.Serializer):
    # mock 支付不接收金额：应付金额由服务端按订单算，避免客户端改价。
    trade_no = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")


class PaymentCallbackSerializer(serializers.Serializer):
    order_no = serializers.CharField(max_length=32)
    trade_no = serializers.CharField(max_length=64)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    timestamp = serializers.IntegerField()
    sign = serializers.CharField(max_length=128)


class OrderItemSerializer(serializers.ModelSerializer):
    sku_id = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = OrderItem
        fields = ["sku_id", "sku_code", "title", "unit_price", "qty", "subtotal"]


class OrderListSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Order
        fields = [
            "order_no",
            "status",
            "status_label",
            "total_amount",
            "discount_amount",
            "pay_amount",
            "expire_at",
            "created_at",
        ]


class OrderDetailSerializer(OrderListSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta(OrderListSerializer.Meta):
        fields = [
            *OrderListSerializer.Meta.fields,
            "items",
            "remark",
            "cancel_reason",
            "paid_at",
            "closed_at",
        ]
