import datetime
import logging

import psycopg2
import psycopg2.extras
import requests
from flask import Flask, jsonify, render_template, request

import geo
import settings

logging.basicConfig(filename=settings.LOG_FILE, level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("branch-locator")

app = Flask(__name__, template_folder=settings.TEMPLATE_DIR)


def branches():
    conn = psycopg2.connect(host=settings.DB_HOST, dbname=settings.DB_NAME,
                            user=settings.DB_USER, password=settings.DB_PASSWORD)
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


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/nearest")
def api_nearest():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify(error="q is required"), 400
    lat, lon = locate(q)
    now = datetime.datetime.now().strftime("%H:%M")
    rows = geo.nearest(branches(), lat, lon, now)
    log.info("nearest q=%s -> %s", q, [r["name"] for r in rows])
    return jsonify(query=q, lat=lat, lon=lon, branches=rows)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=settings.PORT)
