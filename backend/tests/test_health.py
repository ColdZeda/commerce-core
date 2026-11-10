"""探针契约：两者都通 200，任一失败 503 且失败项为 false。"""

import pytest

from health import views


@pytest.mark.django_db
def test_health_ok(client):
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": True, "redis": True}


@pytest.mark.django_db
@pytest.mark.parametrize("broken", ["db", "redis"])
def test_health_503_when_dependency_down(client, monkeypatch, broken):
    monkeypatch.setattr(views, f"_check_{broken}", lambda: False)

    response = client.get("/api/v1/health")
    payload = response.json()

    assert response.status_code == 503
    assert payload["status"] == "error"
    assert payload[broken] is False
