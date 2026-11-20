from rest_framework import serializers

from .models import Address


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ["id", "receiver", "phone", "region", "detail", "is_default", "created_at"]
        read_only_fields = ["id", "created_at"]


class AddressWriteSerializer(serializers.Serializer):
    receiver = serializers.CharField(max_length=40)
    phone = serializers.CharField(max_length=20)
    region = serializers.CharField(max_length=120)
    detail = serializers.CharField(max_length=200)
    is_default = serializers.BooleanField(required=False, default=False)

    def validate_phone(self, value):
        # 只挡明显不是手机号的值，不做运营商号段校验——演示站没有真实短信通道。
        digits = value.strip().replace(" ", "").replace("-", "")
        if not digits.isdigit() or not 7 <= len(digits) <= 15:
            raise serializers.ValidationError("请填 7 到 15 位数字")
        return digits
