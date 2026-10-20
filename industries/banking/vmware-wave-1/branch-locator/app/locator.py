import datetime
import logging
import sys
from zoneinfo import ZoneInfo

import psycopg2
import psycopg2.extras
import requests
from flask import Flask, jsonify, render_template, request

import geo
import settings

logging.basicConfig(stream=sys.stdout, level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("branch-locator")

app = Flask(__name__)


def branches():
    extra = {"sslmode": settings.DB_SSLMODE} if settings.DB_SSLMODE else {}
    conn = psycopg2.connect(host=settings.DB_HOST, dbname=settings.DB_NAME,
                            user=settings.DB_USER, password=settings.DB_PASSWORD,
                            connect_timeout=settings.DB_CONNECT_TIMEOUT, **extra)
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT name, address, lat, lon, opens, closes FROM branches ORDER BY branch_id")
        return cur.fetchall()
    finally:
        conn.close()


def locate(q):
    r = requests.get(settings.GEO_URL, params={"q": q}, timeout=5)
    r.raise_for_status()
    body = r.json()
    return float(body["lat"]), float(body["lon"])


def now_hhmm():
    tz = ZoneInfo(settings.BRANCH_TZ) if settings.BRANCH_TZ else None
    return datetime.datetime.now(tz).strftime("%H:%M")


@app.route("/health")
def health():
    return jsonify(status="ok")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/nearest")
def api_nearest():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify(error="q is required"), 400
    lat, lon = locate(q)
    now = now_hhmm()
    rows = geo.nearest(branches(), lat, lon, now)
    log.info("nearest q=%s -> %s", q, [r["name"] for r in rows])
    return jsonify(query=q, lat=lat, lon=lon, branches=rows)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=settings.PORT)
