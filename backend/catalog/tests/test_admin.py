"""admin 必须能真的改价格与库存，不只看页面能不能打开。"""

from decimal import Decimal

import pytest
from django.urls import reverse

from catalog.tests.factories import make_product, make_sku


@pytest.mark.django_db
def test_admin_can_update_sku_price_and_stock(admin_client):
    product = make_product(name="后台商品")
    sku = make_sku(product, sku_code="ADM-1", price="100.00", stock=5)

    change_url = reverse("admin:catalog_product_change", args=[product.pk])
    assert admin_client.get(change_url).status_code == 200

    response = admin_client.post(
        change_url,
        {
            "name": product.name,
            "subtitle": "",
            "description": "",
            "cover_url": "",
            "is_active": "on",
            "skus-TOTAL_FORMS": "1",
            "skus-INITIAL_FORMS": "1",
            "skus-MIN_NUM_FORMS": "0",
            "skus-MAX_NUM_FORMS": "1000",
            "skus-0-id": str(sku.pk),
            "skus-0-product": str(product.pk),
            "skus-0-sku_code": sku.sku_code,
            "skus-0-title": sku.title,
            "skus-0-price": "168.00",
            "skus-0-stock": "3",
            "skus-0-is_active": "on",
            "_save": "保存",
        },
    )
    assert response.status_code == 302, response.content[:800]

    sku.refresh_from_db()
    assert sku.price == Decimal("168.00")
    assert sku.stock == 3
