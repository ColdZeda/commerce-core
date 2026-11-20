"""评价写入：一批要么全成、要么全不成，避免"评了两个失败一个"的半截状态。"""

from django.db import transaction
from rest_framework import status

from common.errors import BusinessError
from trade.models import Order, OrderItem

from .models import Review


def create_reviews(user, order_no: str, entries: list[dict]) -> list[Review]:
    """给一单里勾中的明细写评价。

    抛 BusinessError：NOT_FOUND / REVIEW_ORDER_NOT_PAID / REVIEW_ALREADY_EXISTS / REVIEW_PRODUCT_GONE。
    """
    with transaction.atomic():
        order = Order.objects.filter(order_no=order_no, user=user).first()
        if order is None:
            # 他人订单一律 404，和订单接口口径一致。
            raise BusinessError("NOT_FOUND", "订单不存在", status.HTTP_404_NOT_FOUND)
        if order.status != Order.Status.PAID:
            raise BusinessError("REVIEW_ORDER_NOT_PAID", "只有已支付的订单可以评价", status.HTTP_409_CONFLICT)

        item_ids = [entry["order_item_id"] for entry in entries]
        items = {
            item.pk: item
            for item in OrderItem.objects.select_related("sku").filter(order=order, pk__in=item_ids)
        }
        # 传了不属于这单的明细，当成"不存在"，不区分"别人的"和"压根没有"。
        missing = [item_id for item_id in item_ids if item_id not in items]
        if missing:
            raise BusinessError("NOT_FOUND", f"明细 {missing[0]} 不属于这个订单", status.HTTP_404_NOT_FOUND)

        if Review.objects.filter(order_item_id__in=item_ids).exists():
            raise BusinessError("REVIEW_ALREADY_EXISTS", "这些商品里有的已经评过了", status.HTTP_409_CONFLICT)

        reviews = []
        for entry in entries:
            item = items[entry["order_item_id"]]
            if item.sku is None:
                raise BusinessError("REVIEW_PRODUCT_GONE", "商品已不存在，无法评价", status.HTTP_409_CONFLICT)
            reviews.append(
                Review(
                    user=user,
                    order_item=item,
                    product_id=item.sku.product_id,
                    rating=entry["rating"],
                    content=entry.get("content", ""),
                )
            )
        return Review.objects.bulk_create(reviews)
