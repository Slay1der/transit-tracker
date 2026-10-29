"""The Ikorodu to CMS corridor (roughly the Lagos BRT route), as stops with coordinates."""
import math

STOPS = [
    ("Ikorodu", 6.6194, 3.5105),
    ("Mile 12", 6.6045, 3.3966),
    ("Ketu", 6.5980, 3.3880),
    ("Ojota", 6.5870, 3.3800),
    ("Maryland", 6.5720, 3.3660),
    ("Fadeyi", 6.5300, 3.3700),
    ("Yaba", 6.5095, 3.3711),
    ("CMS", 6.4540, 3.3940),
]


def haversine_km(lat1, lng1, lat2, lng2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _cumulative():
    out, total = [], 0.0
    for i, (name, lat, lng) in enumerate(STOPS):
        if i:
            _, plat, plng = STOPS[i - 1]
            total += haversine_km(plat, plng, lat, lng)
        out.append((name, lat, lng, round(total, 3)))
    return out


ROUTE = _cumulative()
ROUTE_KM = ROUTE[-1][3]
STOP_KM = {name: km for name, _, _, km in ROUTE}


def position_at(km):
    """Latitude and longitude at a distance along the route (km from Ikorodu)."""
    km = max(0.0, min(km, ROUTE_KM))
    for (n1, la1, lo1, k1), (n2, la2, lo2, k2) in zip(ROUTE, ROUTE[1:]):
        if km <= k2:
            f = 0 if k2 == k1 else (km - k1) / (k2 - k1)
            return la1 + (la2 - la1) * f, lo1 + (lo2 - lo1) * f
    return ROUTE[-1][1], ROUTE[-1][2]


def next_stop(km, direction):
    """The next stop a bus will reach, given its position and direction (+1 towards CMS, -1 towards Ikorodu)."""
    stops = ROUTE if direction > 0 else list(reversed(ROUTE))
    for name, _, _, skm in stops:
        if (direction > 0 and skm > km) or (direction < 0 and skm < km):
            return name
    return stops[-1][0]
