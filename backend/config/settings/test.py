"""测试环境：沿用真实 MySQL/Redis，仅压低哈希成本与日志噪音。"""

from .base import *  # noqa: F401,F403

DEBUG = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

DATABASES["default"]["TEST"] = {"NAME": env("MYSQL_TEST_DATABASE", "test_commerce")}

# 测试里 .delay() 直接在本进程执行，不依赖 worker；调度行为由 phase5 的真实演练验证。
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

ENABLE_MOCK_PAY = True
PAY_CALLBACK_SECRET = "test-pay-secret"
