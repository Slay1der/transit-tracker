import time

import fakeredis
import pytest
from fastapi.testclient import TestClient

from app import main


@pytest.fixture
def client(monkeypatch):
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(main, "r", fake)
    now = time.time()
    for bus_id, km, direction in [("BUS-01", 10.0, 1), ("BUS-02", 30.0, -1), ("BUS-03", 5.0, 1)]:
        fake.hset(f"bus:{bus_id}", mapping={"id": bus_id, "lat": 6.5, "lng": 3.4, "km": km, "direction": direction,
                                             "speed_kmh": 30, "next_stop": "Yaba", "updated_at": now})
        fake.sadd("buses", bus_id)
    fake.hset("bus:BUS-03", "updated_at", now - 999)  # stale bus: must be ignored by /eta
    return TestClient(main.app)


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_buses(client):
    body = client.get("/buses").json()
    assert len(body) == 3
    assert [b for b in body if b["id"] == "BUS-03"][0]["stale"] is True


def test_eta_only_counts_buses_heading_to_the_stop(client):
    body = client.get("/eta/yaba").json()
    ids = [b["bus"] for b in body["buses"]]
    assert body["stop"] == "Yaba"
    assert "BUS-01" in ids and "BUS-02" in ids
    assert "BUS-03" not in ids


def test_unknown_stop(client):
    assert client.get("/eta/Lekki").status_code == 404


def test_metrics(client):
    client.get("/buses")
    text = client.get("/metrics").text
    assert "http_requests_total" in text and "transit_buses_tracked 3.0" in text
