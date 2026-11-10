"""测试环境：沿用真实 MySQL/Redis，仅压低哈希成本与日志噪音。"""

from .base import *  # noqa: F401,F403

DEBUG = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

DATABASES["default"]["TEST"] = {"NAME": env("MYSQL_TEST_DATABASE", "test_commerce")}
