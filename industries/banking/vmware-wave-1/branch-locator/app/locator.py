import datetime
import logging
import sys

import psycopg
from psycopg.rows import dict_row
import requests
from flask import Flask, jsonify, render_template, request

import geo
import settings

logging.basicConfig(stream=sys.stdout, level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("branch-locator")

app = Flask(__name__)
app.json.compact = True
app.json.sort_keys = True
app.json.ensure_ascii = True


def branches():
    conn = psycopg.connect(host=settings.DB_HOST, dbname=settings.DB_NAME,
                           port=settings.DB_PORT, user=settings.DB_USER,
                           password=settings.DB_PASSWORD, connect_timeout=5)
    try:
        cur = conn.cursor(row_factory=dict_row)
        cur.execute("SELECT name, address, lat, lon, opens, closes FROM branches ORDER BY branch_id")
        return cur.fetchall()
    finally:
        conn.close()


def locate(q):
    r = requests.get(settings.GEO_URL, params={"q": q}, timeout=5)
    r.raise_for_status()
    body = r.json()
    return float(body["lat"]), float(body["lon"])


@app.route("/")
def index():
    return render_template("index.html")


def branch_time(now=None):
    now = now or datetime.datetime.now(datetime.timezone.utc)
    return now.astimezone(settings.BRANCH_TZ).strftime("%H:%M")


@app.route("/health")
def health():
    try:
        branches()
        locate("harbour")
    except (psycopg.Error, requests.RequestException, ValueError, KeyError):
        log.exception("readiness check failed")
        return jsonify(status="unavailable"), 503
    return jsonify(status="ok")


@app.route("/api/nearest")
def api_nearest():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify(error="q is required"), 400
    lat, lon = locate(q)
    now = branch_time()
    rows = geo.nearest(branches(), lat, lon, now)
    log.info("nearest q=%s -> %s", q, [r["name"] for r in rows])
    return jsonify(query=q, lat=lat, lon=lon, branches=rows)
