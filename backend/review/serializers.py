from rest_framework import serializers

from .models import Review


def mask_username(username: str) -> str:
    """公开页只露首字符，别把用户名整串挂在免登录接口上。"""
    if not username:
        return "匿名"
    return f"{username[0]}***"


class ReviewSerializer(serializers.ModelSerializer):
    username = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ["id", "rating", "content", "username", "created_at"]

    def get_username(self, obj):
        return mask_username(obj.user.username)


class ReviewEntrySerializer(serializers.Serializer):
    order_item_id = serializers.IntegerField(min_value=1)
    rating = serializers.IntegerField(min_value=1, max_value=5)
    content = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class ReviewCreateSerializer(serializers.Serializer):
    reviews = ReviewEntrySerializer(many=True, allow_empty=False)

    def validate_reviews(self, reviews):
        if len(reviews) > 20:
            raise serializers.ValidationError("一次最多评 20 个")
        # 同一批里重复传同一条明细，落库时会撞唯一约束，提前拦掉更清楚。
        if len({item["order_item_id"] for item in reviews}) != len(reviews):
            raise serializers.ValidationError("同一条明细只能评一次")
        return reviews
