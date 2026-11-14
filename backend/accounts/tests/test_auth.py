"""登录、刷新、me 的契约：401 要能区分过期与伪造。"""

import json
from datetime import timedelta

import jwt
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

pytestmark = pytest.mark.django_db

FORGED_KEY = "not-the-project-signing-key-for-tests"


def forged_token(**claims):
    payload = {"token_type": "access", "jti": "forged", "user_id": 1, "exp": 9999999999}
    payload.update(claims)
    return jwt.encode(payload, FORGED_KEY, algorithm="HS256")


@pytest.fixture
def user():
    return get_user_model().objects.create_user(username="alice", password="pw-alice-123")


def post_json(client, name, payload):
    return client.post(reverse(name), data=json.dumps(payload), content_type="application/json")


def test_login_returns_tokens_and_user(client, user):
    response = post_json(client, "auth-login", {"username": "alice", "password": "pw-alice-123"})

    body = response.json()
    assert response.status_code == 200
    assert body["user"] == {"id": user.id, "username": "alice", "is_staff": False}
    assert body["access"] and body["refresh"]


def test_login_with_wrong_password_returns_business_code(client, user):
    response = post_json(client, "auth-login", {"username": "alice", "password": "wrong-password"})

    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_INVALID_CREDENTIALS"


def test_me_without_token_is_token_invalid(client):
    response = client.get(reverse("auth-me"))

    assert response.status_code == 401
    assert response.json()["code"] == "TOKEN_INVALID"


def test_me_with_garbage_token_is_token_invalid(client):
    response = client.get(reverse("auth-me"), HTTP_AUTHORIZATION="Bearer not-a-token")

    assert response.status_code == 401
    assert response.json()["code"] == "TOKEN_INVALID"


def test_me_with_expired_token_is_token_expired(client, user):
    token = AccessToken.for_user(user)
    token.set_exp(lifetime=timedelta(seconds=-10))

    response = client.get(reverse("auth-me"), HTTP_AUTHORIZATION=f"Bearer {token}")

    assert response.status_code == 401
    assert response.json()["code"] == "TOKEN_EXPIRED"


def test_me_with_valid_token_returns_current_user(client, user):
    token = AccessToken.for_user(user)

    response = client.get(reverse("auth-me"), HTTP_AUTHORIZATION=f"Bearer {token}")

    assert response.status_code == 200
    assert response.json()["username"] == "alice"


def test_refresh_returns_new_access(client, user):
    refresh = RefreshToken.for_user(user)

    response = post_json(client, "auth-refresh", {"refresh": str(refresh)})

    assert response.status_code == 200
    assert response.json()["access"]


def test_refresh_with_expired_token_is_token_expired(client, user):
    refresh = RefreshToken.for_user(user)
    refresh.set_exp(lifetime=timedelta(seconds=-10))

    response = post_json(client, "auth-refresh", {"refresh": str(refresh)})

    assert response.status_code == 401
    assert response.json()["code"] == "TOKEN_EXPIRED"


@pytest.mark.parametrize("exp", ["not-a-number", None, [], {}])
def test_me_with_malformed_exp_is_token_invalid(client, exp):
    response = client.get(reverse("auth-me"), HTTP_AUTHORIZATION=f"Bearer {forged_token(exp=exp)}")

    assert response.status_code == 401
    assert response.json()["code"] == "TOKEN_INVALID"


def test_me_with_forged_expired_token_is_token_invalid(client):
    # 未验签就读 exp，会把伪造 token 判成"过期"，前端于是静默刷新而不是回登录页。
    response = client.get(reverse("auth-me"), HTTP_AUTHORIZATION=f"Bearer {forged_token(exp=1)}")

    assert response.status_code == 401
    assert response.json()["code"] == "TOKEN_INVALID"


@pytest.mark.parametrize("exp", ["not-a-number", None])
def test_refresh_with_malformed_exp_is_token_invalid(client, exp):
    response = post_json(client, "auth-refresh", {"refresh": forged_token(token_type="refresh", exp=exp)})

    assert response.status_code == 401
    assert response.json()["code"] == "TOKEN_INVALID"
