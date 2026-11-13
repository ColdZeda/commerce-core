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
