"""商品只读接口：列表带最低在售价，详情带在售 SKU 与库存。"""

from django.db.models import Min, Prefetch, Q
from rest_framework import generics
from rest_framework.exceptions import NotFound, ValidationError

from config.pagination import StandardPagination

from .models import SKU, Product
from .serializers import ProductDetailSerializer, ProductListSerializer


class ProductListView(generics.ListAPIView):
    serializer_class = ProductListSerializer
    pagination_class = StandardPagination

    # 白名单决定可排序字段；列表里没有单 SKU 价，价格一律按最低在售价排。
    ORDERING_MAP = {
        "created_at": "created_at",
        "-created_at": "-created_at",
        "price": "min_price",
        "-price": "-min_price",
    }
    DEFAULT_ORDERING = "-created_at"

    def get_queryset(self):
        ordering = self.request.query_params.get("ordering", self.DEFAULT_ORDERING)
        if ordering not in self.ORDERING_MAP:
            raise ValidationError({"ordering": [f"允许的排序字段：{', '.join(sorted(self.ORDERING_MAP))}"]})

        queryset = (
            Product.objects.filter(is_active=True)
            .annotate(min_price=Min("skus__price", filter=Q(skus__is_active=True)))
            .order_by(self.ORDERING_MAP[ordering], "-id")
        )

        keyword = self.request.query_params.get("keyword", "").strip()
        if keyword:
            queryset = queryset.filter(Q(name__icontains=keyword) | Q(subtitle__icontains=keyword))
        return queryset


class ProductDetailView(generics.RetrieveAPIView):
    serializer_class = ProductDetailSerializer

    def get_queryset(self):
        return Product.objects.filter(is_active=True).prefetch_related(
            Prefetch(
                "skus",
                queryset=SKU.objects.filter(is_active=True).order_by("id"),
                to_attr="active_skus",
            )
        )

    # 统一错误体的 message 是给人看的，默认的 "No Product matches..." 太暴露实现细节。
    def get_object(self):
        product = self.get_queryset().filter(pk=self.kwargs["pk"]).first()
        if product is None:
            raise NotFound("商品不存在")
        return product
