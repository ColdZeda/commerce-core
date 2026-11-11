"""订单：创建（含幂等重放）、列表、详情、取消、模拟支付、支付回调；业务规则全在 services。"""

import uuid

from django.conf import settings
from django.db.models import Prefetch
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.errors import BusinessError
from config.pagination import StandardPagination

from .models import Order, OrderItem
from .payments import verify_payload
from .serializers import (
    OrderCancelSerializer,
    OrderCreateSerializer,
    OrderDetailSerializer,
    OrderListSerializer,
    OrderPaySerializer,
    PaymentCallbackSerializer,
)
from .services import cancel_order, create_order, mark_order_paid

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


class OrderPayView(APIView):
    """mock 支付入口：金额取订单自己的应付，客户端没有机会改价。"""

    permission_classes = [IsAuthenticated]

    def post(self, request, order_no: str):
        if not settings.ENABLE_MOCK_PAY:
            raise BusinessError("PAY_NOT_ENABLED", "模拟支付未开启", status.HTTP_403_FORBIDDEN)

        payload = OrderPaySerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        order = Order.objects.filter(order_no=order_no, user=request.user).first()
        if order is None:
            raise NotFound("订单不存在")

        trade_no = payload.validated_data["trade_no"] or f"MOCK{uuid.uuid4().hex[:16].upper()}"
        paid, already = mark_order_paid(order.order_no, order.pay_amount, trade_no)
        headers = {"X-Idempotent-Replay": "1"} if already else {}
        return Response(OrderDetailSerializer(_load_with_items(paid)).data, headers=headers)


class PaymentCallbackView(APIView):
    """第三方回调：没有 JWT，身份由 HMAC 证明。"""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        payload = PaymentCallbackSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        verify_payload(data["order_no"], data["trade_no"], data["amount"], data["timestamp"], data["sign"])

        order, already = mark_order_paid(data["order_no"], data["amount"], data["trade_no"])
        return Response(
            {
                "order_no": order.order_no,
                "status": order.status,
                "status_label": order.get_status_display(),
                "pay_amount": str(order.pay_amount),
                "paid_at": order.paid_at.isoformat() if order.paid_at else None,
                "idempotent": already,
            }
        )
