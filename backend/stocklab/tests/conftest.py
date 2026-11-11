"""实验区共用 fixture：Redis 只清 lab: 前缀，不碰同一实例上的其它数据。"""

import pytest
import redis
from django.conf import settings

from stocklab.redis_reserve import PREFIX


def clear_lab_keys(client) -> None:
    for key in client.scan_iter(f"{PREFIX}*"):
        client.delete(key)


@pytest.fixture
def lab_redis():
    client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    clear_lab_keys(client)
    yield client
    clear_lab_keys(client)
