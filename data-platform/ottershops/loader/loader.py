"""OtterShops Postgres -> Snowflake RAW incremental loader, followed by `dbt build`.

Every LOAD_INTERVAL_SECONDS (default 300):
  * orders (+ lines, fees) and customers changed since the last watermark are appended to RAW;
  * products, collections and stores are re-snapshotted when their content hash changes;
  * SKU stock is snapshotted in full once per day and for changed SKUs on every run;
  * dbt builds STAGING and MARTS and runs its tests.
Staging models de-duplicate appended rows by key, so re-loading is always safe.
"""
import datetime as dt
import hashlib
import json
import logging
import os
import pathlib
import subprocess
import sys
import time

import psycopg
import snowflake.connector
from cryptography.hazmat.primitives import serialization

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s loader %(message)s", stream=sys.stdout)
log = logging.getLogger()
snowflake.connector.paramstyle = "qmark"

PG_DSN = os.environ.get("PG_DSN", "postgresql://ottershops:ottershops_dev@localhost:5432/ottershops")
INTERVAL = int(os.environ.get("LOAD_INTERVAL_SECONDS", "300"))
DBT_DIR = pathlib.Path(os.environ.get("DBT_PROJECT_DIR", pathlib.Path(__file__).resolve().parent.parent / "dbt"))
EPOCH = "1970-01-01T00:00:00+00:00"

RAW_TABLES = {
    "ORDERS": """id string, order_number string, customer_id string, email string, status string, fulfillment string,
        shipping_method string, store_id string, ship_city string, ship_state string, ship_zip string, promo_code string,
        subtotal_cents number, discount_cents number, shipping_cents number, fees_cents number, tax_cents number,
        total_cents number, payment_provider string, card_brand string, card_last4 string,
        created_at timestamp_tz, updated_at timestamp_tz""",
    "ORDER_LINES": """order_id string, line_no number, sku string, product_id string, name string, color string, size string,
        quantity number, unit_list_cents number, unit_price_cents number, discount_cents number, line_total_cents number""",
    "ORDER_FEES": "order_id string, code string, label string, amount_cents number",
    "CUSTOMERS": "id string, email string, first_name string, last_name string, rewards_points number, created_at timestamp_tz, updated_at timestamp_tz",
    "PRODUCTS": """id string, name string, label string, department string, category string, fit string,
        list_price_cents number, markdown_price_cents number, rating float, review_count number, is_new boolean, created_at timestamp_tz""",
    "PRODUCT_COLLECTIONS": "product_id string, collection_slug string",
    "STORES": "id string, name string, address string, city string, state string, zip string, pickup_enabled boolean, pickup_ready_hours number",
    "SKU_SNAPSHOTS": "sku string, product_id string, color string, color_family string, size string, stock number, snapshot_at timestamp_tz",
}

ORDER_COLS = ("id, order_number, customer_id, email, status, fulfillment, shipping_method, store_id, ship_city, ship_state, ship_zip, "
              "promo_code, subtotal_cents, discount_cents, shipping_cents, fees_cents, tax_cents, total_cents, payment_provider, "
              "card_brand, card_last4, created_at, updated_at")
SNAPSHOTS = {
    "PRODUCTS": "select id, name, label, department, category, fit, list_price_cents, markdown_price_cents, rating::float8, review_count, is_new, created_at from products order by id",
    "PRODUCT_COLLECTIONS": "select product_id, collection_slug from product_collections order by 1, 2",
    "STORES": "select id, name, address, city, state, zip, pickup_enabled, pickup_ready_hours from stores order by id",
}


def norm(v):
    if isinstance(v, dt.datetime):
        return v.isoformat()
    if v is None or isinstance(v, (int, float, str, bool)):
        return v
    return str(v)


def snowflake_conn():
    key = serialization.load_pem_private_key(pathlib.Path(os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"]).read_bytes(), password=None)
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ.get("SNOWFLAKE_USER", "OTTERSHOPS_SVC"),
        private_key=key.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()),
        role="OTTERSHOPS_PIPELINE", warehouse="OTTERSHOPS_WH", database="OTTERSHOPS", schema="RAW",
        session_parameters={"QUERY_TAG": "ottershops-loader"},
    )


class Loader:
    def __init__(self, sf):
        self.sf = sf
        cur = sf.cursor()
        for name, cols in RAW_TABLES.items():
            cur.execute(f"create table if not exists RAW.{name} ({cols}, _loaded_at timestamp_tz default current_timestamp())")
        cur.execute("create table if not exists RAW.LOAD_STATE (name string, value string, updated_at timestamp_tz)")
        self.state = dict(cur.execute("select name, value from RAW.LOAD_STATE").fetchall())
        self.stock = dict(cur.execute(
            "select sku, stock from RAW.SKU_SNAPSHOTS qualify row_number() over (partition by sku order by snapshot_at desc) = 1"
        ).fetchall())

    def put_state(self, name, value):
        self.sf.cursor().execute(
            "merge into RAW.LOAD_STATE t using (select ? as name, ? as value) s on t.name = s.name "
            "when matched then update set value = s.value, updated_at = current_timestamp() "
            "when not matched then insert (name, value, updated_at) values (s.name, s.value, current_timestamp())",
            (name, value))
        self.state[name] = value

    def insert(self, table, cols, rows, loaded_at):
        if not rows:
            return 0
        names = [c.strip().split(" ")[0] for c in cols.split(",")]
        marks = ", ".join("?" for _ in names)
        self.sf.cursor().executemany(
            f"insert into RAW.{table} ({', '.join(names)}, _loaded_at) values ({marks}, ?)",
            [tuple(norm(v) for v in r) + (loaded_at,) for r in rows])
        return len(rows)

    def run_once(self, pg):
        now = dt.datetime.now(dt.timezone.utc)
        loaded_at = now.isoformat()
        counts = {}
        # Orders, lines, fees
        wm = self.state.get("orders_wm", EPOCH)
        orders = pg.execute(f"select {ORDER_COLS} from orders where updated_at > %s order by updated_at", (wm,)).fetchall()
        if orders:
            ids = [o[0] for o in orders]
            counts["orders"] = self.insert("ORDERS", RAW_TABLES["ORDERS"], orders, loaded_at)
            counts["order_lines"] = self.insert("ORDER_LINES", RAW_TABLES["ORDER_LINES"], pg.execute(
                "select order_id, line_no, sku, product_id, name, color, size, quantity, unit_list_cents, unit_price_cents, "
                "discount_cents, line_total_cents from order_lines where order_id = any(%s)", (ids,)).fetchall(), loaded_at)
            counts["order_fees"] = self.insert("ORDER_FEES", RAW_TABLES["ORDER_FEES"], pg.execute(
                "select order_id, code, label, amount_cents from order_fees where order_id = any(%s)", (ids,)).fetchall(), loaded_at)
            self.put_state("orders_wm", orders[-1][-1].isoformat())
        # Customers (never the password hash)
        wm = self.state.get("customers_wm", EPOCH)
        customers = pg.execute("select id, email, first_name, last_name, rewards_points, created_at, updated_at from customers "
                               "where updated_at > %s order by updated_at", (wm,)).fetchall()
        if customers:
            counts["customers"] = self.insert("CUSTOMERS", RAW_TABLES["CUSTOMERS"], customers, loaded_at)
            self.put_state("customers_wm", customers[-1][-1].isoformat())
        # Small reference tables: reload on change
        for table, sql in SNAPSHOTS.items():
            rows = pg.execute(sql).fetchall()
            digest = hashlib.sha256(json.dumps([[norm(v) for v in r] for r in rows]).encode()).hexdigest()
            if self.state.get(f"{table}_hash") != digest:
                counts[table.lower()] = self.insert(table, RAW_TABLES[table], rows, loaded_at)
                self.put_state(f"{table}_hash", digest)
        # Inventory: full snapshot once per day, otherwise changed SKUs only
        skus = pg.execute("select sku, product_id, color, color_family, size, stock from skus").fetchall()
        full = self.state.get("sku_full_date") != now.date().isoformat()
        changed = [s for s in skus if full or self.stock.get(s[0]) != s[5]]
        if changed:
            counts["sku_snapshots"] = self.insert("SKU_SNAPSHOTS", RAW_TABLES["SKU_SNAPSHOTS"], [s + (loaded_at,) for s in changed], loaded_at)
            self.stock.update({s[0]: s[5] for s in changed})
        if full:
            self.put_state("sku_full_date", now.date().isoformat())
        return counts


def dbt_build():
    cmd = ["dbt", "build", "--project-dir", str(DBT_DIR), "--profiles-dir", str(DBT_DIR), "--log-format", "text"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    tail = [l for l in res.stdout.splitlines() if "Done." in l or "ERROR" in l or "FAIL" in l]
    (log.info if res.returncode == 0 else log.error)("dbt build exit=%s %s", res.returncode, " | ".join(tail[-5:]))
    return res.returncode == 0


def main():
    once = "--once" in sys.argv
    key = pathlib.Path(os.environ.get("SNOWFLAKE_PRIVATE_KEY_PATH", ""))
    if not key.is_file() or key.stat().st_size == 0:
        log.warning("no Snowflake key at %s; loader idle. Set OTTERSHOPS_SNOWFLAKE_KEY_FILE to enable.", key)
        while True:
            time.sleep(3600)
    sf = snowflake_conn()
    loader = Loader(sf)
    first = True
    while True:
        started = time.monotonic()
        try:
            with psycopg.connect(PG_DSN) as pg:
                counts = loader.run_once(pg)
            log.info("loaded %s", json.dumps(counts) if counts else "nothing new")
            ok = dbt_build() if (counts or first) else True
            first = False
            if once:
                sys.exit(0 if ok else 1)
        except Exception:
            log.exception("load cycle failed")
            if once:
                sys.exit(1)
        time.sleep(max(5, INTERVAL - (time.monotonic() - started)))


if __name__ == "__main__":
    main()
