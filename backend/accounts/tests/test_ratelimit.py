"""限流：注册按 IP、登录按 IP 与用户名各一道，超限返回 429 且不误伤正常访问。"""

import pytest
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse

pytestmark = pytest.mark.django_db

REGISTER = {"username": "limiter-1", "password": "shop-pass-8848", "password_confirm": "shop-pass-8848"}


@pytest.fixture(autouse=True)
def clear_counters():
    # 计数在 Redis 里跨用例保留，不清理会让后一个用例接着前一个的计数往上走。
    cache.clear()
    yield
    cache.clear()


def register(client, index=1, ip="10.0.0.1"):
    payload = {
        **REGISTER,
        "username": f"limiter-{index}",
    }
    return client.post(
        reverse("auth-register"),
        payload,
        content_type="application/json",
        HTTP_X_FORWARDED_FOR=ip,
    )


def login(client, username="probe", password="whatever-123", ip="10.0.0.2"):
    return client.post(
        reverse("auth-login"),
        {"username": username, "password": password},
        content_type="application/json",
        HTTP_X_FORWARDED_FOR=ip,
    )


@override_settings(RATELIMIT_ENABLED=True, RATELIMIT_REGISTER=3)
def test_register_is_limited_per_ip(client):
    for index in range(1, 4):
        assert register(client, index=index).status_code == 201

    blocked = register(client, index=4)

    assert blocked.status_code == 429
    assert blocked.json()["code"] == "TOO_MANY_REQUESTS"
    assert blocked["Retry-After"] == "3600"


@override_settings(RATELIMIT_ENABLED=True, RATELIMIT_REGISTER=1)
def test_register_limit_is_per_ip_not_global(client):
    assert register(client, index=1, ip="10.1.0.1").status_code == 201
    assert register(client, index=2, ip="10.1.0.2").status_code == 201
    # 同一个 IP 再来一次才被挡
    assert register(client, index=3, ip="10.1.0.1").status_code == 429


@override_settings(RATELIMIT_ENABLED=True, RATELIMIT_LOGIN_USER=2)
def test_login_is_limited_per_username(client):
    for _ in range(2):
        assert login(client, username="target").status_code == 401

    blocked = login(client, username="target")

    assert blocked.status_code == 429
    assert blocked.json()["code"] == "TOO_MANY_REQUESTS"


@override_settings(RATELIMIT_ENABLED=True, RATELIMIT_LOGIN_USER=2)
def test_login_user_limit_ignores_case(client):
    login(client, username="Target")
    login(client, username="target")

    # 大小写不同也算同一个账号，否则换个大小写就能接着猜。
    assert login(client, username="TARGET").status_code == 429


@override_settings(RATELIMIT_ENABLED=True, RATELIMIT_LOGIN_USER=100, RATELIMIT_LOGIN_IP=3)
def test_login_is_limited_per_ip_across_usernames(client):
    for index in range(3):
        assert login(client, username=f"user-{index}").status_code == 401

    blocked = login(client, username="user-x")

    assert blocked.status_code == 429


@override_settings(RATELIMIT_ENABLED=True, RATELIMIT_LOGIN_IP=2)
def test_login_ip_limit_is_per_ip(client):
    login(client, ip="10.2.0.1")
    login(client, ip="10.2.0.1")
    assert login(client, ip="10.2.0.1").status_code == 429
    assert login(client, ip="10.2.0.2").status_code == 401


@override_settings(RATELIMIT_ENABLED=False)
def test_switch_off_disables_limiting(client):
    for index in range(1, 5):
        assert register(client, index=index).status_code == 201


@override_settings(RATELIMIT_ENABLED=True, RATELIMIT_REGISTER=1)
def test_counter_expires_so_the_block_is_not_permanent(client):
    assert register(client, index=1).status_code == 201
    assert register(client, index=2).status_code == 429

    # 窗口过去后计数应从头开始；直接删键就等于模拟了一次过期。
    cache.delete("ratelimit:register:10.0.0.1")
    assert register(client, index=3).status_code == 201
