"""Celery 应用：broker 复用 Redis，配置全部来自 Django settings 的 CELERY_* 前缀。"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("commerce_core")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
