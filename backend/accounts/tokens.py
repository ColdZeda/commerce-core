"""区分"过期"和"伪造/损坏"：前端据此决定是静默刷新还是回登录页。"""

from rest_framework_simplejwt.exceptions import ExpiredTokenError


def classify_token_failure(raw_token: str, token_class) -> str:
    """按验签后的结论分类；调用方只在 token 已被判失败时进来。"""
    try:
        token_class(raw_token)
    except ExpiredTokenError:
        return "TOKEN_EXPIRED"
    except Exception:
        # 只认验签结论：未验签的 exp 既可伪造，畸形值还会把分类打成 500。
        return "TOKEN_INVALID"
    return "TOKEN_INVALID"
