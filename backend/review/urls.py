from django.urls import path

from .views import OrderReviewView, ProductReviewView

urlpatterns = [
    path("products/<int:pk>/reviews", ProductReviewView.as_view(), name="product-reviews"),
    path("orders/<str:order_no>/review", OrderReviewView.as_view(), name="order-review"),
]
