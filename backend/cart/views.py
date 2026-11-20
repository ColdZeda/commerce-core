"""购物车接口：列表带合计，写操作把 409 业务码留给 service 判断。"""

from decimal import Decimal

from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import SKU

from .models import CartItem
from .serializers import (
    AddItemSerializer,
    CartItemSerializer,
    SelectAllSerializer,
    UpdateItemSerializer,
)
from .services import add_item, remove_item, set_all_selected, update_item


def cart_snapshot(user) -> dict:
    """购物车全量：行、总件数、总金额，以及"勾中的"件数与金额（结算按它算）。"""
    items = list(CartItem.objects.filter(user=user).select_related("sku__product").order_by("-id"))
    total_amount = sum((item.sku.price * item.qty for item in items), Decimal("0.00"))
    picked = [item for item in items if item.selected]
    return {
        "items": CartItemSerializer(items, many=True).data,
        "total_qty": sum(item.qty for item in items),
        "total_amount": str(total_amount),
        "selected_qty": sum(item.qty for item in picked),
        "selected_amount": str(sum((item.sku.price * item.qty for item in picked), Decimal("0.00"))),
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

    def patch(self, request):
        """整车的全选 / 取消全选。"""
        serializer = SelectAllSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        set_all_selected(request.user, serializer.validated_data["selected"])
        return Response(cart_snapshot(request.user))


class CartItemDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        serializer = UpdateItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        update_item(
            request.user,
            pk,
            qty=serializer.validated_data.get("qty"),
            selected=serializer.validated_data.get("selected"),
        )
        return Response(cart_snapshot(request.user))

    def delete(self, request, pk):
        remove_item(request.user, pk)
        return Response(cart_snapshot(request.user), status=status.HTTP_200_OK)
