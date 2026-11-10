"""商品接口契约：只暴露在售商品、金额字符串、分页与排序白名单。"""

import pytest
from django.urls import reverse

from catalog.tests.factories import make_product, make_sku


@pytest.mark.django_db
def test_list_returns_only_active_products_with_min_price(client):
    visible = make_product(name="在售商品")
    make_sku(visible, price="10.00")
    make_sku(visible, price="25.50")
    make_product(name="下架商品", is_active=False)

    response = client.get(reverse("product-list"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["results"][0]["name"] == "在售商品"
    assert payload["results"][0]["min_price"] == "10.00"


@pytest.mark.django_db
def test_page_size_defaults_to_ten_and_caps_at_fifty(client):
    for index in range(60):
        product = make_product(name=f"商品{index:02d}")
        make_sku(product, price="1.00")

    default_page = client.get(reverse("product-list")).json()
    assert default_page["count"] == 60
    assert len(default_page["results"]) == 10
    assert default_page["next"] is not None

    capped_page = client.get(reverse("product-list"), {"page_size": 200}).json()
    assert len(capped_page["results"]) == 50


@pytest.mark.django_db
def test_keyword_matches_name_or_subtitle(client):
    make_product(name="青轴键盘", subtitle="段落感强")
    make_product(name="红轴键盘", subtitle="线性手感")
    make_product(name="显示器支架", subtitle="桌面")

    payload = client.get(reverse("product-list"), {"keyword": "键盘"}).json()
    assert payload["count"] == 2

    payload = client.get(reverse("product-list"), {"keyword": "桌面"}).json()
    assert payload["count"] == 1
    assert payload["results"][0]["name"] == "显示器支架"


@pytest.mark.django_db
def test_ordering_by_price_ignores_inactive_skus(client):
    cheap = make_product(name="便宜")
    make_sku(cheap, price="9.00")
    pricey = make_product(name="贵")
    make_sku(pricey, price="999.00")
    make_sku(pricey, price="1.00", is_active=False)

    payload = client.get(reverse("product-list"), {"ordering": "price"}).json()

    assert [item["name"] for item in payload["results"]] == ["便宜", "贵"]
    assert payload["results"][1]["min_price"] == "999.00"


@pytest.mark.django_db
def test_ordering_outside_whitelist_returns_400(client):
    response = client.get(reverse("product-list"), {"ordering": "name"})

    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION_ERROR"


@pytest.mark.django_db
def test_detail_returns_active_skus_and_404_for_missing(client):
    product = make_product(name="详情商品")
    active = make_sku(product, price="88.00", stock=7)
    make_sku(product, price="11.00", is_active=False)

    response = client.get(reverse("product-detail", args=[product.pk]))
    payload = response.json()

    assert response.status_code == 200
    assert payload["min_price"] == "88.00"
    assert [item["sku_code"] for item in payload["skus"]] == [active.sku_code]
    assert payload["skus"][0]["stock"] == 7

    missing = client.get(reverse("product-detail", args=[999_999]))
    assert missing.status_code == 404
    assert missing.json() == {"code": "NOT_FOUND", "message": "商品不存在"}


@pytest.mark.django_db
def test_list_query_count_stays_constant(client, django_assert_num_queries):
    for index in range(12):
        product = make_product(name=f"批量{index:02d}")
        make_sku(product, price="5.00")
        make_sku(product, price="6.00")

    with django_assert_num_queries(2):
        response = client.get(reverse("product-list"), {"page_size": 10})
    assert len(response.json()["results"]) == 10


@pytest.mark.django_db
def test_detail_query_count_stays_constant(client, django_assert_num_queries):
    product = make_product()
    for _ in range(3):
        make_sku(product, price="5.00")

    with django_assert_num_queries(2):
        response = client.get(reverse("product-detail", args=[product.pk]))
    assert response.status_code == 200
