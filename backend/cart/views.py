"""购物车接口：列表带合计，写操作把 409 业务码留给 service 判断。"""

from decimal import Decimal

from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import SKU

from .models import CartItem
from .serializers import AddItemSerializer, CartItemSerializer, UpdateQtySerializer
from .services import add_item, remove_item, update_qty


def cart_snapshot(user) -> dict:
    """购物车全量：行、总件数、总金额，一次查询带出 SKU 与商品。"""
    items = list(CartItem.objects.filter(user=user).select_related("sku__product").order_by("-id"))
    total_amount = sum((item.sku.price * item.qty for item in items), Decimal("0.00"))
    return {
        "items": CartItemSerializer(items, many=True).data,
        "total_qty": sum(item.qty for item in items),
        "total_amount": str(total_amount),
    }


class CartItemListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(cart_snapshot(request.user))

    def post(self, request):
        serializer = AddItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        sku = SKU.objects.select_related("product").filter(pk=serializer.validated_data["sku_id"]).first()
        if sku is None:
            raise ValidationError({"sku_id": ["SKU 不存在"]})

        add_item(request.user, sku, serializer.validated_data["qty"])
        return Response(cart_snapshot(request.user), status=status.HTTP_201_CREATED)


class CartItemDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        serializer = UpdateQtySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        update_qty(request.user, pk, serializer.validated_data["qty"])
        return Response(cart_snapshot(request.user))

    def delete(self, request, pk):
        remove_item(request.user, pk)
        return Response(cart_snapshot(request.user), status=status.HTTP_200_OK)
