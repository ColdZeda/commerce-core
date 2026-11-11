"""本地开发：打开 DEBUG，宽松主机头方便局域网调试。"""

from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ["*"]
# 本地演示要能点「模拟支付」，默认开；想验证关闭态就在 .env 里设 false。
ENABLE_MOCK_PAY = env("ENABLE_MOCK_PAY", "true").strip().lower() in {"1", "true", "yes"}
