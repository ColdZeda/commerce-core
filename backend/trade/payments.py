"""回调签名：把 order_no|trade_no|amount|timestamp 用 HMAC-SHA256 签成十六进制串。"""

import hashlib
import hmac
import time
from decimal import Decimal

from django.conf import settings
from rest_framework import status

from common.errors import BusinessError

SIGN_INVALID = "PAY_SIGN_INVALID"


def sign_payload(order_no: str, trade_no: str, amount, timestamp: int) -> str:
    message = f"{order_no}|{trade_no}|{_amount_text(amount)}|{timestamp}"
    return hmac.new(settings.PAY_CALLBACK_SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()


def verify_payload(order_no: str, trade_no: str, amount, timestamp: int, sign: str) -> None:
    """校验时间窗与签名；不通过抛 BusinessError(PAY_SIGN_INVALID, 401)。"""
    if abs(int(time.time()) - int(timestamp)) > settings.PAY_CALLBACK_WINDOW_SECONDS:
        raise BusinessError(SIGN_INVALID, "回调时间超出允许范围", status.HTTP_401_UNAUTHORIZED)
    if not hmac.compare_digest(sign_payload(order_no, trade_no, amount, timestamp), sign):
        raise BusinessError(SIGN_INVALID, "签名校验失败", status.HTTP_401_UNAUTHORIZED)


def _amount_text(amount) -> str:
    # 金额固定两位小数参与签名，避免 94 与 94.00 签出两个不同结果。
    return f"{Decimal(str(amount)):.2f}"
