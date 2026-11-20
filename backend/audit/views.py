"""`/audit` 免登录只读：谁都能点开看账平不平，这是"库存守恒"的可视化证据。"""

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import build_report


class AuditView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(build_report())
