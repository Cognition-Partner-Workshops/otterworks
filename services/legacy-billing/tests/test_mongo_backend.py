import json
import os
import sys
from pathlib import Path

import oracledb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import facade as facade_module

from app import app

pytestmark = pytest.mark.skipif(
    not (os.getenv("MONGO_LOCAL_URI") and os.getenv("OW_BILLING_FIXTURE_DSN")),
    reason="requires MONGO_LOCAL_URI and OW_BILLING_FIXTURE_DSN",
)

INVOICES_SQL = """SELECT i.id AS invoice_id, rp.period_start, rp.period_end,
          i.subtotal, i.tax, i.total, c.code_desc AS status
     FROM invoices i
     JOIN rating_periods rp ON rp.id = i.period_id
     LEFT JOIN codes c
       ON c.code_type = 'INV_STATUS'
      AND c.code_val = i.status_cd
    WHERE i.tenant_id = :1
    ORDER BY i.issued_at DESC, i.id DESC"""


def _dsn():
    return json.loads(os.environ["OW_BILLING_FIXTURE_DSN"])


def _oracle_conn():
    dsn = _dsn()
    host, _, rest = dsn["dsn"].partition(":")
    port, _, service = rest.partition("/")
    return oracledb.connect(
        user=dsn["user"],
        password=dsn["password"],
        host=host,
        port=int(port),
        service_name=service,
    )


@pytest.fixture()
def mongo(monkeypatch):
    monkeypatch.setenv("BILLING_BACKEND", "mongo")
    monkeypatch.setenv("MONGO_URI_SECRET", "MONGO_LOCAL_URI")
    from backends import mongo

    yield mongo
    mongo._client = None


@pytest.fixture()
def oracle(monkeypatch):
    dsn = _dsn()
    host, _, rest = dsn["dsn"].partition(":")
    port, _, service = rest.partition("/")
    monkeypatch.setenv("ORACLE_USER", dsn["user"])
    monkeypatch.setenv("ORACLE_PASSWORD", dsn["password"])
    monkeypatch.setenv("ORACLE_HOST", host)
    monkeypatch.setenv("ORACLE_PORT", port)
    monkeypatch.setenv("ORACLE_SERVICE", service)
    from backends import oracle

    return oracle


def _tenant_ids():
    with _oracle_conn() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT DISTINCT tenant_id FROM invoices ORDER BY 1")
        return [row[0] for row in cursor]


def _invoice_ids():
    with _oracle_conn() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT id FROM invoices ORDER BY 1")
        return [row[0] for row in cursor]


def test_invoices_parity(mongo, oracle):
    for tenant_id in _tenant_ids():
        mongo_rows = mongo.invoices(tenant_id)
        oracle_rows = oracle.query(INVOICES_SQL, (tenant_id,))
        assert len(mongo_rows) == len(oracle_rows)
        # codes collection is owned by unit u-00 and is absent locally;
        # status is None on the mongo side, so compare with it excluded.
        for m_row, o_row in zip(mongo_rows, oracle_rows):
            m_status = m_row.pop("status")
            assert m_status is None
            o_row.pop("status")
            assert m_row == o_row


def test_invoice_lines_parity(mongo, oracle):
    for invoice_id in _invoice_ids():
        assert mongo.invoice_lines(invoice_id) == oracle.invoice_lines(invoice_id)


def test_invoice_owned(mongo):
    invoice_id = _invoice_ids()[0]
    with _oracle_conn() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT tenant_id FROM invoices WHERE id = :1", (invoice_id,)
        )
        tenant_id = cursor.fetchone()[0]
    assert mongo.invoice_owned(invoice_id, tenant_id) is True
    assert mongo.invoice_owned(invoice_id, "nobody") is False


def test_facade_mongo_routes(mongo):
    tenant_id = _tenant_ids()[0]
    client = app.test_client()
    response = client.get(
        "/api/v1/billing/invoices", headers={"X-User-ID": tenant_id}
    )
    assert response.status_code == 200
    assert response.get_json() == mongo.invoices(tenant_id)

    invoice_id = _invoice_ids()[0]
    with _oracle_conn() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT tenant_id FROM invoices WHERE id = :1", (invoice_id,)
        )
        owner = cursor.fetchone()[0]
    foreign = "nobody" if owner != "nobody" else "somebody"
    response = client.get(
        f"/api/v1/billing/invoices/{invoice_id}/lines",
        headers={"X-User-ID": foreign},
    )
    assert response.status_code == 404


def test_facade_mongo_does_not_ensure(mongo, monkeypatch):
    monkeypatch.setattr(
        facade_module, "_ensure", lambda _: pytest.fail("Oracle was touched")
    )
    client = app.test_client()
    response = client.get(
        "/api/v1/billing/invoices", headers={"X-User-ID": _tenant_ids()[0]}
    )
    assert response.status_code == 200
