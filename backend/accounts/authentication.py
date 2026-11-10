"""把 simplejwt 的异常翻译成带业务码的 401。"""

from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken

from .tokens import classify_token_failure


class BearerAuthentication(JWTAuthentication):
    def get_validated_token(self, raw_token):
        try:
            return super().get_validated_token(raw_token)
        except (InvalidToken, TokenError):
            raise AuthenticationFailed(
                "登录状态已失效",
                code=classify_token_failure(raw_token, AccessToken),
            ) from None
