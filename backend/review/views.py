"""评论接口：商品页免登录可读，写评价只对本人已支付的订单开放。"""

from django.db.models import Avg, Count
from rest_framework import generics, status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Product
from config.pagination import StandardPagination

from .models import Review
from .serializers import ReviewCreateSerializer, ReviewSerializer
from .services import create_reviews


def product_rating(product_id: int) -> dict:
    stats = Review.objects.filter(product_id=product_id).aggregate(count=Count("id"), average=Avg("rating"))
    average = stats["average"]
    return {
        "count": stats["count"],
        # 平均分留一位小数，前端直接显示，不用再处理浮点尾巴。
        "average": round(float(average), 1) if average is not None else None,
    }


class ProductReviewView(generics.ListAPIView):
    serializer_class = ReviewSerializer
    pagination_class = StandardPagination
    permission_classes = [AllowAny]

    def get_queryset(self):
        return Review.objects.filter(product_id=self.kwargs["pk"]).select_related("user")

    def get(self, request, *args, **kwargs):
        # 商品不存在时按 404 处理，别让"没评论"和"没商品"混成同一个空列表。
        if not Product.objects.filter(pk=kwargs["pk"], is_active=True).exists():
            raise NotFound("商品不存在")
        return super().get(request, *args, **kwargs)

    def get_paginated_response(self, data):
        return Response(
            {**super().get_paginated_response(data).data, "summary": product_rating(self.kwargs["pk"])}
        )


class OrderReviewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_no: str):
        payload = ReviewCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        reviews = create_reviews(request.user, order_no, payload.validated_data["reviews"])
        return Response(
            {"created": len(reviews), "items": ReviewSerializer(reviews, many=True).data},
            status=status.HTTP_201_CREATED,
        )
