"""Lagos Transit Tracker API.

Reads the bus positions the worker writes to Redis and answers:
  GET /health          is the API up and can it reach Redis?
  GET /stops           stops on the route
  GET /buses           latest position of every bus
  GET /eta/{stop}      which buses are coming to a stop, and roughly when
  GET /metrics         Prometheus metrics
"""
import logging
import os
import time

import redis
from fastapi import FastAPI, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

from .route import ROUTE, STOP_KM

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
STALE_AFTER_SECONDS = float(os.getenv("STALE_AFTER_SECONDS", "30"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s level=%(levelname)s service=api %(message)s")
log = logging.getLogger("api")

app = FastAPI(title="Lagos Transit Tracker")
r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "path", "status"])
LATENCY = Histogram("http_request_duration_seconds", "Request latency", ["path"])
TRACKED = Gauge("transit_buses_tracked", "Buses with a position in Redis")
FRESHEST = Gauge("transit_newest_position_age_seconds", "Age of the most recent bus position")


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    route = request.scope.get("route")
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        route = request.scope.get("route")
        path = route.path if route else "unmatched"
        if path != "/metrics":
            REQUESTS.labels(request.method, path, str(status)).inc()
            LATENCY.labels(path).observe(time.perf_counter() - start)
            log.info("msg=request method=%s path=%s status=%s", request.method, request.url.path, status)


def load_buses():
    ids = sorted(r.smembers("buses"))
    pipe = r.pipeline()
    for i in ids:
        pipe.hgetall(f"bus:{i}")
    now = time.time()
    buses = []
    for raw in pipe.execute():
        if not raw:
            continue
        age = now - float(raw["updated_at"])
        buses.append({
            "id": raw["id"],
            "lat": float(raw["lat"]),
            "lng": float(raw["lng"]),
            "km": float(raw["km"]),
            "direction": "to CMS" if int(raw["direction"]) > 0 else "to Ikorodu",
            "speed_kmh": float(raw["speed_kmh"]),
            "next_stop": raw["next_stop"],
            "age_seconds": round(age, 1),
            "stale": age > STALE_AFTER_SECONDS,
        })
    TRACKED.set(len(buses))
    if buses:
        FRESHEST.set(min(b["age_seconds"] for b in buses))
    return buses


@app.get("/health")
def health():
    try:
        r.ping()
    except redis.RedisError as e:
        log.error("msg=health_failed error=%r", e)
        raise HTTPException(status_code=503, detail="redis unreachable")
    return {"status": "ok"}


@app.get("/stops")
def stops():
    return [{"name": n, "lat": la, "lng": lo, "km_from_ikorodu": km} for n, la, lo, km in ROUTE]


@app.get("/buses")
def buses():
    try:
        return load_buses()
    except redis.RedisError as e:
        log.error("msg=redis_error error=%r", e)
        raise HTTPException(status_code=503, detail="redis unreachable")


@app.get("/eta/{stop}")
def eta(stop: str):
    match = next((s for s in STOP_KM if s.lower() == stop.lower()), None)
    if match is None:
        raise HTTPException(status_code=404, detail=f"unknown stop '{stop}'. Try /stops")
    stop_km = STOP_KM[match]
    try:
        fleet = load_buses()
    except redis.RedisError:
        raise HTTPException(status_code=503, detail="redis unreachable")
    coming = []
    for b in fleet:
        if b["stale"]:
            continue
        ahead = (stop_km - b["km"]) if b["direction"] == "to CMS" else (b["km"] - stop_km)
        if ahead <= 0:
            continue
        speed = max(b["speed_kmh"], 5.0)  # never divide by a bus stuck in traffic
        coming.append({"bus": b["id"], "direction": b["direction"], "km_away": round(ahead, 2), "eta_minutes": round(ahead / speed * 60, 1)})
    coming.sort(key=lambda x: x["eta_minutes"])
    return {"stop": match, "buses": coming[:5]}


@app.get("/metrics")
def metrics():
    try:
        load_buses()
    except redis.RedisError:
        pass
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
