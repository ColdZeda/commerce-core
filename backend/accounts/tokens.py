"""区分"过期"和"伪造/损坏"：前端据此决定是静默刷新还是回登录页。"""

import time

from rest_framework_simplejwt.exceptions import TokenError


def classify_token_failure(raw_token: str, token_class) -> str:
    try:
        token_class(raw_token, verify=False)
    except Exception:
        return "TOKEN_INVALID"

    try:
        payload = token_class(raw_token, verify=False).payload
    except TokenError:
        return "TOKEN_INVALID"

    expire_at = payload.get("exp")
    if expire_at is None or int(expire_at) < int(time.time()):
        return "TOKEN_EXPIRED"
    # 结构正常、也没过期，却没过验签：换过密钥或被人改过。
    return "TOKEN_INVALID"
