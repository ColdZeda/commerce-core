"""演示账号命令：口令来自环境变量或随机生成，且不落进仓库与日志。"""

import io
import re

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

pytestmark = pytest.mark.django_db

User = get_user_model()


def run(**options):
    out = io.StringIO()
    call_command("create_demo_user", stdout=out, **options)
    return out.getvalue()


def test_uses_password_from_env_and_does_not_print_it(monkeypatch):
    monkeypatch.setenv("DEMO_PASSWORD", "pw-from-env-123")

    output = run()

    user = User.objects.get(username="demo")
    assert user.check_password("pw-from-env-123")
    assert "pw-from-env-123" not in output


def test_generated_password_is_printed_once_and_works(monkeypatch):
    monkeypatch.delenv("DEMO_PASSWORD", raising=False)

    output = run()

    match = re.search(r"随机口令（只显示这一次）：(\S+)", output)
    assert match, output
    assert User.objects.get(username="demo").check_password(match.group(1))


def test_second_run_keeps_existing_password(monkeypatch):
    monkeypatch.setenv("DEMO_PASSWORD", "first-pw-123")
    run()

    monkeypatch.setenv("DEMO_PASSWORD", "second-pw-456")
    output = run()

    assert "已存在" in output
    assert User.objects.get(username="demo").check_password("first-pw-123")


def test_reset_replaces_password(monkeypatch):
    monkeypatch.setenv("DEMO_PASSWORD", "first-pw-123")
    run()

    monkeypatch.setenv("DEMO_PASSWORD", "second-pw-456")
    run(reset=True)

    user = User.objects.get(username="demo")
    assert user.check_password("second-pw-456")
    assert not user.check_password("first-pw-123")


def test_staff_flag_creates_admin(monkeypatch):
    monkeypatch.setenv("DEMO_PASSWORD", "admin-pw-123")

    output = run(username="admin", staff=True)

    user = User.objects.get(username="admin")
    assert user.is_staff is True
    assert "管理员账号" in output


def test_plain_account_is_not_staff(monkeypatch):
    monkeypatch.setenv("DEMO_PASSWORD", "demo-pw-123")

    run()

    assert User.objects.get(username="demo").is_staff is False


def test_staff_flag_promotes_an_existing_account_without_touching_password(monkeypatch):
    monkeypatch.setenv("DEMO_PASSWORD", "keep-me-123")
    run(username="promote")

    output = run(username="promote", staff=True)

    user = User.objects.get(username="promote")
    # 只补权限，口令不动：不该为了进后台逼人改口令。
    assert user.is_staff is True
    assert user.check_password("keep-me-123")
    assert "已补成管理员" in output
