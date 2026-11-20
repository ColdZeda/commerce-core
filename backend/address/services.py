"""地址写操作：同一用户最多一条默认地址，靠"先全清再置位"保证。"""

from django.db import transaction
from rest_framework import status

from common.errors import BusinessError

from .models import Address


def _mark_default(user, address: Address) -> None:
    with transaction.atomic():
        Address.objects.filter(user=user).exclude(pk=address.pk).update(is_default=False)
        Address.objects.filter(pk=address.pk).update(is_default=True)


def create_address(user, **fields) -> Address:
    wanted = fields.pop("is_default", False)
    # 第一条地址自动成为默认，否则新用户进来没有默认地址，结算还得多点一次。
    first = not Address.objects.filter(user=user).exists()
    with transaction.atomic():
        address = Address.objects.create(user=user, is_default=first or wanted, **fields)
    if address.is_default:
        _mark_default(user, address)
    return address


def update_address(user, address_id: int, **fields) -> Address:
    address = Address.objects.filter(pk=address_id, user=user).first()
    if address is None:
        raise BusinessError("NOT_FOUND", "地址不存在", status.HTTP_404_NOT_FOUND)

    make_default = fields.pop("is_default", False)
    if fields:
        for key, value in fields.items():
            setattr(address, key, value)
        address.save(update_fields=[*fields.keys(), "updated_at"])
    if make_default:
        _mark_default(user, address)
    return Address.objects.get(pk=address.pk)


def delete_address(user, address_id: int) -> None:
    address = Address.objects.filter(pk=address_id, user=user).first()
    if address is None:
        raise BusinessError("NOT_FOUND", "地址不存在", status.HTTP_404_NOT_FOUND)

    was_default = address.is_default
    address.delete()
    # 删掉默认地址后把剩下的最新一条顶上来，避免用户以为还有默认地址却选不到。
    if was_default:
        fallback = Address.objects.filter(user=user).order_by("-id").first()
        if fallback is not None:
            Address.objects.filter(pk=fallback.pk).update(is_default=True)
