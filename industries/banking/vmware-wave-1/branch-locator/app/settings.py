# Settings for branch-locator, read from the environment (deploy/values.yaml).
# DB_PASSWORD arrives through secretEnv from the secret store; there is no default.
import os

DB_HOST = os.environ.get("DB_HOST", "wave1-db")
DB_NAME = os.environ.get("DB_NAME", "bankwave")
DB_USER = os.environ.get("DB_USER", "branch_app")
DB_PASSWORD = os.environ["DB_PASSWORD"]
DB_SSLMODE = os.environ.get("DB_SSLMODE", "")
DB_CONNECT_TIMEOUT = int(os.environ.get("DB_CONNECT_TIMEOUT", "5"))

GEO_URL = os.environ.get("GEO_URL", "http://geo.bank.internal:8090/geocode")

# Zone for open_now. Unset keeps the host clock's zone, as on web-02.
BRANCH_TZ = os.environ.get("BRANCH_TZ", "")

PORT = int(os.environ.get("PORT", "8080"))
