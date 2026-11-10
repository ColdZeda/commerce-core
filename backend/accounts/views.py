from django.contrib.auth import authenticate
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import LoginSerializer, UserSerializer
from .tokens import classify_token_failure


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request,
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
        )
        if user is None or not user.is_active:
            raise AuthenticationFailed("用户名或密码错误", code="AUTH_INVALID_CREDENTIALS")

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data,
            }
        )


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
