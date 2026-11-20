"""建一个演示账号；密码不写进仓库，来自环境变量或现场随机生成。

公网 demo 需要一个能登录的账号，但把固定口令写进 README 等于把它提交进 Git。
所以这里只负责"建账号"，口令由部署者决定：给 DEMO_PASSWORD 就用它，
不给就生成一个随机口令并只打印这一次。
"""

import os
import secrets

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

DEFAULT_USERNAME = "demo"


class Command(BaseCommand):
    help = "创建或重置演示账号；密码取自 DEMO_PASSWORD，未设置则随机生成并打印一次"

    def add_arguments(self, parser):
        parser.add_argument("--username", default=DEFAULT_USERNAME)
        parser.add_argument(
            "--staff",
            action="store_true",
            help="建的是管理员账号（is_staff=True），能进 /admin/",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="账号已存在时重设密码（默认跳过，避免每次部署把口令改掉）",
        )

    def handle(self, *args, **options):
        username = options["username"]
        reset = options["reset"]
        want_staff = options["staff"]

        User = get_user_model()
        user = User.objects.filter(username=username).first()
        if user is not None and not reset:
            # 已存在时只补权限：先建普通号、后来想让它进后台，不该逼人 --reset 换口令。
            if want_staff and not user.is_staff:
                user.is_staff = True
                user.save(update_fields=["is_staff"])
                self.stdout.write(f"账号 {username} 已存在，已补成管理员")
            else:
                self.stdout.write(f"账号 {username} 已存在，跳过（要重设密码加 --reset）")
            return

        password = os.environ.get("DEMO_PASSWORD", "")
        generated = not password
        if generated:
            password = secrets.token_urlsafe(12)

        if user is None:
            User.objects.create_user(username=username, password=password, is_staff=want_staff)
            action = "已创建"
        else:
            user.set_password(password)
            user.is_staff = want_staff
            user.save(update_fields=["password", "is_staff"])
            action = "已重设密码"

        role = "管理员" if want_staff else "普通用户"
        self.stdout.write(f"{role}账号 {username} {action}")
        if generated:
            self.stdout.write(f"随机口令（只显示这一次）：{password}")
            self.stdout.write("想自己指定就设置环境变量 DEMO_PASSWORD 后加 --reset 重跑")
        else:
            self.stdout.write("口令取自环境变量 DEMO_PASSWORD，未打印")
