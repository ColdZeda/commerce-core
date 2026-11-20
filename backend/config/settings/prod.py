"""Linux 镜像运行：DEBUG 关闭，静态文件交给 nginx。"""

from .base import *  # noqa: F401,F403

DEBUG = False

CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

# 静态文件由 whitenoise 发（Dockerfile 里 collectstatic 打进镜像），nginx 只把 /static/ 转过来。
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}
