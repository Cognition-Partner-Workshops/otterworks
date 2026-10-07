"""Run the billing-service FastAPI app, unchanged, inside the VPC.

The shared instance is reachable only from its private subnets, so the service
runs here and scripts/billing-service-proxy.py on the operator's machine turns
local HTTP requests into lambda:Invoke calls. Each event carries:

- "db": engine/host/port/dbname/username/password of the run's login role (the
  otterworks-<token>/billing-db secret, read by the proxy; there is no Secrets
  Manager endpoint in these subnets). Never logged.
- "allow_internal_reset": whether POST /internal/reset may rewrite the data
  (BILLING_SVC_ALLOW_INTERNAL_RESET of the container); false unless asked for.
- "http": an API Gateway HTTP API (2.0) request, answered by Mangum.
"""

import os

from psycopg.conninfo import make_conninfo

CA_BUNDLE = os.path.join(os.path.dirname(__file__), "rds-ca.pem")

_handler = None


def _conninfo(db):
    return make_conninfo(
        host=db["host"], port=int(db["port"]), dbname=db["dbname"],
        user=db["username"], password=db["password"],
        sslmode="verify-full", sslrootcert=CA_BUNDLE, connect_timeout=10,
        application_name=os.environ.get("AWS_LAMBDA_FUNCTION_NAME", "billing-service"),
    )


def _app_handler(event):
    global _handler
    if _handler is None:
        os.environ["BILLING_SVC_DATABASE_URL"] = _conninfo(event["db"])
        from mangum import Mangum

        from app.db import migrate
        from app.main import app

        migrate()  # what the service's lifespan does at container start
        _handler = Mangum(app, lifespan="off")
    from app.config import settings

    settings.database_url = _conninfo(event["db"])
    settings.allow_internal_reset = bool(event.get("allow_internal_reset", False))
    return _handler


def handler(event, context):
    return _app_handler(event)(event["http"], context)
