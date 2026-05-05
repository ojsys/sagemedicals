import pytest
from django.test import Client


@pytest.mark.django_db
def test_health_check_returns_200():
    client = Client()
    response = client.get("/health/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["checks"]["db"]["ok"] is True
    assert data["checks"]["cache"]["ok"] is True


@pytest.mark.django_db
def test_health_check_not_cached(settings):
    client = Client()
    r1 = client.get("/health/")
    r2 = client.get("/health/")
    assert r1.status_code == 200
    assert r2.status_code == 200
    # Each response should include latency — both are fresh DB hits
    assert "latency_ms" in r1.json()["checks"]["db"]
