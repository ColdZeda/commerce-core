from django.urls import path

from .views import (
    OrderCancelView,
    OrderDetailView,
    OrderListCreateView,
    OrderPayView,
    PaymentCallbackView,
)

urlpatterns = [
    path("orders", OrderListCreateView.as_view(), name="order-list"),
    path("orders/<str:order_no>", OrderDetailView.as_view(), name="order-detail"),
    path("orders/<str:order_no>/cancel", OrderCancelView.as_view(), name="order-cancel"),
    path("orders/<str:order_no>/pay", OrderPayView.as_view(), name="order-pay"),
    path("payments/callback", PaymentCallbackView.as_view(), name="payment-callback"),
]
