import math


def distance_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def is_open(opens, closes, hhmm):
    return opens <= hhmm < closes


def nearest(branches, lat, lon, hhmm, limit=3):
    rows = []
    for b in branches:
        d = distance_km(lat, lon, float(b["lat"]), float(b["lon"]))
        row = dict(b)
        row["lat"], row["lon"] = float(b["lat"]), float(b["lon"])
        row["km"] = round(d, 2)
        row["open_now"] = is_open(b["opens"], b["closes"], hhmm)
        rows.append(row)
    rows.sort(key=lambda r: r["km"])
    return rows[:limit]
