from django.urls import path

from .views import CartItemDetailView, CartItemListView

urlpatterns = [
    path("cart/items", CartItemListView.as_view(), name="cart-items"),
    path("cart/items/<int:pk>", CartItemDetailView.as_view(), name="cart-item-detail"),
]
