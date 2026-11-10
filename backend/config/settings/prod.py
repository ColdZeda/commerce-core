"""Linux 镜像运行：DEBUG 关闭，静态文件交给 nginx。"""

from .base import *  # noqa: F401,F403

DEBUG = False

CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
