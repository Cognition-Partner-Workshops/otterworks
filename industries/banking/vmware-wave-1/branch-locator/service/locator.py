import datetime
import logging
import sys
from zoneinfo import ZoneInfo

import psycopg2
import psycopg2.extras
import requests
from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

import geo
import settings

logging.basicConfig(stream=sys.stdout, level=settings.LOG_LEVEL,
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("branch-locator")

app = Flask(__name__, template_folder=settings.TEMPLATE_DIR)
BUSINESS_TZ = ZoneInfo(settings.BUSINESS_TZ)

# Error page exactly as Werkzeug 1.0 rendered it on web-02.
ERROR_PAGE = ('<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">\n'
              "<title>{code} {name}</title>\n<h1>{name}</h1>\n{description}\n")


def connect():
    return psycopg2.connect(host=settings.DB_HOST, port=settings.DB_PORT, dbname=settings.DB_NAME,
                            user=settings.DB_USER, password=settings.DB_PASSWORD,
                            connect_timeout=settings.DB_CONNECT_TIMEOUT)


def branches():
    conn = connect()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT name, address, lat, lon, opens, closes FROM branches ORDER BY branch_id")
        return cur.fetchall()
    finally:
        conn.close()


def locate(q):
    r = requests.get(settings.GEO_URL, params={"q": q}, timeout=settings.GEO_TIMEOUT)
    r.raise_for_status()
    body = r.json()
    return float(body["lat"]), float(body["lon"])


def business_hhmm():
    return datetime.datetime.now(BUSINESS_TZ).strftime("%H:%M")


@app.errorhandler(HTTPException)
def http_error(e):
    body = ERROR_PAGE.format(code=e.code, name=e.name, description=e.get_description())
    headers = [(k, v) for k, v in e.get_headers() if k.lower() != "content-type"]
    return body, e.code, headers + [("Content-Type", "text/html; charset=utf-8")]


@app.route("/health")
def health():
    try:
        conn = connect()
        try:
            conn.cursor().execute("SELECT 1")
        finally:
            conn.close()
    except psycopg2.Error as exc:
        log.warning("health: database unreachable: %s", exc.__class__.__name__)
        return jsonify(status="DOWN"), 503
    return jsonify(status="UP")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/nearest")
def api_nearest():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify(error="q is required"), 400
    lat, lon = locate(q)
    rows = geo.nearest(branches(), lat, lon, business_hhmm())
    log.info("nearest q=%s -> %s", q, [r["name"] for r in rows])
    return jsonify(query=q, lat=lat, lon=lon, branches=rows)
