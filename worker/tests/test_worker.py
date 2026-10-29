import random
import sys
from pathlib import Path

import fakeredis

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import worker  # noqa: E402
from route import ROUTE_KM  # noqa: E402


def test_bus_stays_on_route_and_turns_around():
    rng = random.Random(1)
    bus = {"id": "BUS-01", "km": ROUTE_KM - 0.01, "direction": 1, "base_speed": 30}
    for _ in range(50):
        worker.step(bus, 60, rng)
        assert 0 <= bus["km"] <= ROUTE_KM
    assert bus["direction"] == -1


def test_publish_writes_hash_and_stream():
    r = fakeredis.FakeRedis(decode_responses=True)
    bus = {"id": "BUS-07", "km": 5.0, "direction": 1, "base_speed": 25}
    worker.publish(r, bus, 25.0)
    assert r.hget("bus:BUS-07", "next_stop")
    assert "BUS-07" in r.smembers("buses")
    assert r.xlen("positions") == 1
