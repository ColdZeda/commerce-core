"""订单：创建（含幂等重放）、列表、详情、取消；业务规则全在 services。"""

from django.db.models import Prefetch
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from config.pagination import StandardPagination

from .models import Order, OrderItem
from .serializers import (
    OrderCancelSerializer,
    OrderCreateSerializer,
    OrderDetailSerializer,
    OrderListSerializer,
)
from .services import cancel_order, create_order

STATUS_BY_NAME = {
    "pending": Order.Status.PENDING,
    "paid": Order.Status.PAID,
    "cancelled": Order.Status.CANCELLED,
    "closed": Order.Status.CLOSED,
}


def _load_with_items(order: Order) -> Order:
    return Order.objects.prefetch_related(Prefetch("items", queryset=OrderItem.objects.order_by("id"))).get(
        pk=order.pk
    )


class OrderListCreateView(generics.ListAPIView):
    serializer_class = OrderListSerializer
    pagination_class = StandardPagination
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Order.objects.filter(user=self.request.user).order_by("-created_at")
        status_param = self.request.query_params.get("status")
        if status_param:
            if status_param not in STATUS_BY_NAME:
                raise ValidationError({"status": [f"只支持 {', '.join(STATUS_BY_NAME)}"]})
            queryset = queryset.filter(status=STATUS_BY_NAME[status_param])
        return queryset

    def post(self, request):
        payload = OrderCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data

        order, replayed = create_order(
            request.user,
            data["items"],
            user_coupon_id=data.get("user_coupon_id"),
            client_token=data.get("client_token", ""),
            remark=data.get("remark", ""),
        )
        # 重放与首次创建的 body 一致，只多一个头，前端据此判断"这次没真的下单"。
        headers = {"X-Idempotent-Replay": "1"} if replayed else {}
        return Response(
            OrderDetailSerializer(_load_with_items(order)).data,
            status=status.HTTP_200_OK if replayed else status.HTTP_201_CREATED,
            headers=headers,
        )


class OrderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_no: str):
        order = Order.objects.filter(order_no=order_no, user=request.user).first()
        if order is None:
            raise NotFound("订单不存在")
        return Response(OrderDetailSerializer(_load_with_items(order)).data)


class OrderCancelView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_no: str):
        payload = OrderCancelSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        order = cancel_order(request.user, order_no, payload.validated_data["reason"])
        return Response(OrderDetailSerializer(_load_with_items(order)).data)
