"""Fake GPS: pretends to be a fleet of buses driving the Ikorodu to CMS corridor.

Every tick, each bus moves forward a little (speed varies with "traffic"), then:
  - its latest position is saved in the Redis hash  bus:<id>
  - the update is appended to the Redis stream      positions
At the end of the route a bus turns around and drives back.
"""
import logging
import os
import random
import signal
import time

import redis
from prometheus_client import Counter, Gauge, start_http_server

from route import ROUTE_KM, next_stop, position_at

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
NUM_BUSES = int(os.getenv("NUM_BUSES", "20"))
TICK_SECONDS = float(os.getenv("TICK_SECONDS", "5"))
METRICS_PORT = int(os.getenv("METRICS_PORT", "9100"))
STREAM_MAXLEN = 10_000

logging.basicConfig(level=logging.INFO, format="%(asctime)s level=%(levelname)s service=worker %(message)s")
log = logging.getLogger("worker")

POSITIONS = Counter("transit_positions_published_total", "GPS positions published to Redis")
PUBLISH_ERRORS = Counter("transit_publish_errors_total", "Failed publishes to Redis")
BUSES = Gauge("transit_buses_simulated", "Buses being simulated")


def new_fleet(n, rng):
    return [
        {
            "id": f"BUS-{i + 1:02d}",
            "km": rng.uniform(0, ROUTE_KM),
            "direction": rng.choice([1, -1]),
            "base_speed": rng.uniform(18, 35),
        }
        for i in range(n)
    ]


def step(bus, dt, rng):
    """Move one bus forward by dt seconds. Returns its current speed in km/h."""
    traffic = rng.choice([0.2, 0.5, 1.0, 1.0, 1.2])  # Lagos traffic: sometimes you just stand still
    speed = bus["base_speed"] * traffic
    bus["km"] += bus["direction"] * speed * dt / 3600
    if bus["km"] >= ROUTE_KM:
        bus["km"], bus["direction"] = ROUTE_KM, -1
    elif bus["km"] <= 0:
        bus["km"], bus["direction"] = 0.0, 1
    return speed


def publish(r, bus, speed):
    lat, lng = position_at(bus["km"])
    data = {
        "id": bus["id"],
        "lat": round(lat, 6),
        "lng": round(lng, 6),
        "km": round(bus["km"], 3),
        "direction": bus["direction"],
        "speed_kmh": round(speed, 1),
        "next_stop": next_stop(bus["km"], bus["direction"]),
        "updated_at": time.time(),
    }
    pipe = r.pipeline()
    pipe.hset(f"bus:{bus['id']}", mapping=data)
    pipe.sadd("buses", bus["id"])
    pipe.xadd("positions", data, maxlen=STREAM_MAXLEN, approximate=True)
    pipe.execute()
    return data


def run():
    rng = random.Random()
    r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    fleet = new_fleet(NUM_BUSES, rng)
    BUSES.set(len(fleet))
    start_http_server(METRICS_PORT)
    log.info("msg=started buses=%d tick=%ss redis=%s metrics_port=%d", NUM_BUSES, TICK_SECONDS, REDIS_URL, METRICS_PORT)

    stop = {"now": False}
    signal.signal(signal.SIGTERM, lambda *_: stop.update(now=True))

    while not stop["now"]:
        for bus in fleet:
            speed = step(bus, TICK_SECONDS, rng)
            try:
                publish(r, bus, speed)
                POSITIONS.inc()
            except redis.RedisError as e:
                PUBLISH_ERRORS.inc()
                log.error("msg=publish_failed bus=%s error=%r", bus["id"], e)
        time.sleep(TICK_SECONDS)
    log.info("msg=stopping")


if __name__ == "__main__":
    run()
