"""本地开发：打开 DEBUG，宽松主机头方便局域网调试。"""

from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ["*"]
