from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.db import IntegrityError
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed, Throttled, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from common import ratelimit
from promotion.services import grant_welcome_coupon

from .serializers import LoginSerializer, RegisterSerializer, UserSerializer
from .tokens import classify_token_failure

User = get_user_model()


def throttle(key: str, limit: int, window: int) -> None:
    try:
        ratelimit.hit(key, limit, window)
    except ratelimit.RateLimitExceeded as exc:
        raise Throttled(wait=exc.retry_after) from None


def issue_tokens(user) -> dict:
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh), "user": UserSerializer(user).data}


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        ip = ratelimit.client_ip(request)
        throttle(f"register:{ip}", settings.RATELIMIT_REGISTER, settings.RATELIMIT_REGISTER_WINDOW)

        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = User.objects.create_user(
                username=serializer.validated_data["username"],
                password=serializer.validated_data["password"],
            )
        except IntegrityError:
            # 校验通过到写入之间可能被别人抢注，唯一索引兜住后按字段错误返回。
            raise ValidationError({"username": ["用户名已被占用"]}) from None

        grant_welcome_coupon(user)
        return Response(issue_tokens(user), status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data["username"]
        ip = ratelimit.client_ip(request)
        # IP 挡撞库，用户名挡"换个 IP 继续猜同一个账号"，两道都要。
        throttle(f"login-ip:{ip}", settings.RATELIMIT_LOGIN_IP, settings.RATELIMIT_LOGIN_IP_WINDOW)
        throttle(
            f"login-user:{username.lower()}",
            settings.RATELIMIT_LOGIN_USER,
            settings.RATELIMIT_LOGIN_USER_WINDOW,
        )

        user = authenticate(
            request,
            username=username,
            password=serializer.validated_data["password"],
        )
        if user is None or not user.is_active:
            raise AuthenticationFailed("用户名或密码错误", code="AUTH_INVALID_CREDENTIALS")

        return Response(issue_tokens(user))


class RefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        raw_token = request.data.get("refresh")
        if not raw_token:
            raise AuthenticationFailed("缺少 refresh", code="TOKEN_INVALID")

        try:
            refresh = RefreshToken(raw_token)
        except TokenError:
            raise AuthenticationFailed(
                "登录状态已失效",
                code=classify_token_failure(raw_token, RefreshToken),
            ) from None
        return Response({"access": str(refresh.access_token)})


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)
