"""按运行环境选择 MySQL 驱动：Windows 用 PyMySQL 垫片，Linux 镜像用 mysqlclient。

mysqlclient 在 Windows 需要 C 编译链，本地开发装不上；镜像里用 Debian 的 libmariadb 头文件编译，
两者都走 Django 的 mysql 后端，只有驱动来源不同。
"""

import os
import sys

_driver = os.environ.get("DB_DRIVER") or ("pymysql" if sys.platform == "win32" else "mysqlclient")

if _driver == "pymysql":
    import pymysql

    pymysql.install_as_MySQLdb()

# Celery 的 CLI 靠这个属性找应用：celery -A config worker / beat。
from .celery import app as celery_app  # noqa: E402,F401
