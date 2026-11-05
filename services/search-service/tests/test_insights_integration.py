import os

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.services.insights import InsightsClient
from tests.test_insights import ACCOUNT, URL, expected_rows, provision


@pytest.mark.skipif(not all(os.getenv(n) for n in (
    "SNOWFLAKE_EXT_ACCOUNT", "SNOWFLAKE_EXT_USER", "SNOWFLAKE_EXT_PRIVATE_KEY",
)), reason="Snowflake EXT credentials not configured")
def test_live_spec(app, client, monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    with provision.admin_connection() as conn, conn.cursor() as cur:
        for statement in provision.provision_sql(public):
            cur.execute(statement)
    monkeypatch.setenv("SNOWFLAKE_ACCOUNT", os.environ["SNOWFLAKE_EXT_ACCOUNT"])
    backend = InsightsClient(app.config["APP_CONFIG"].insights, private_key=private)
    app.config["INSIGHTS_CLIENT"] = backend
    try:
        expected = expected_rows()
        for kind in (None, "term", "document"):
            query = {"window_end_date": "2026-11-01"}
            if kind:
                query["item_type"] = kind
            response = client.get(URL, query_string=query, headers={"X-User-ID": ACCOUNT})
            assert response.status_code == 200, response.json
            assert response.json["rows"] == [r for r in expected if kind is None or r["item_type"] == kind]
    finally:
        backend.close()
        private = None
        key = None
