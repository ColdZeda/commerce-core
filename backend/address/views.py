"""地址接口：只操作本人的地址，越权一律 404。"""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Address
from .serializers import AddressSerializer, AddressWriteSerializer
from .services import create_address, delete_address, update_address


class AddressListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        addresses = Address.objects.filter(user=request.user)
        return Response({"items": AddressSerializer(addresses, many=True).data})

    def post(self, request):
        payload = AddressWriteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        address = create_address(request.user, **payload.validated_data)
        return Response(AddressSerializer(address).data, status=status.HTTP_201_CREATED)


class AddressDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        payload = AddressWriteSerializer(data=request.data, partial=True)
        payload.is_valid(raise_exception=True)
        address = update_address(request.user, pk, **payload.validated_data)
        return Response(AddressSerializer(address).data)

    def delete(self, request, pk):
        delete_address(request.user, pk)
        return Response(status=status.HTTP_204_NO_CONTENT)
