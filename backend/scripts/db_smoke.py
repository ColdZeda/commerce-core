"""S0 驱动实测：走 Django 的连接（Windows 下是 PyMySQL 垫片）写入再读回。

临时表只在当前会话可见，不落库、不需要迁移，避免为一次性验证污染 schema。
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

import django  # noqa: E402

django.setup()

from django.db import connection  # noqa: E402

MARK = "windows-pymysql"


def main() -> int:
    with connection.cursor() as cursor:
        cursor.execute("SELECT VERSION(), @@character_set_server, @@transaction_isolation")
        version, charset, isolation = cursor.fetchone()

        cursor.execute("CREATE TEMPORARY TABLE s0_smoke (id INT PRIMARY KEY, note VARCHAR(32)) ENGINE=InnoDB")
        cursor.execute("INSERT INTO s0_smoke (id, note) VALUES (1, %s)", [MARK])
        cursor.execute("SELECT note FROM s0_smoke WHERE id = 1")
        note = cursor.fetchone()[0]
        cursor.execute("DROP TEMPORARY TABLE s0_smoke")

    print(f"server={version} charset={charset} isolation={isolation}")
    print(f"roundtrip={note}")
    return 0 if note == MARK else 1


if __name__ == "__main__":
    raise SystemExit(main())
