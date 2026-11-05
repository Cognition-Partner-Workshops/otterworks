"""branch-locator settings, read from the environment (no defaults for credentials)."""
import os

DB_HOST = os.environ.get("DB_HOST", "wave1-db")
DB_PORT = int(os.environ.get("DB_PORT", "5432"))
DB_NAME = os.environ.get("DB_NAME", "bankwave")
DB_USER = os.environ.get("DB_USER", "branch_app")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_CONNECT_TIMEOUT = int(os.environ.get("DB_CONNECT_TIMEOUT", "3"))

GEO_URL = os.environ.get("GEO_URL", "http://geo.bank.internal:8090/geocode")
GEO_TIMEOUT = float(os.environ.get("GEO_TIMEOUT", "5"))

# Zone used for "open now". web-02 ran on the host clock with no zone set (UTC).
BUSINESS_TZ = os.environ.get("BUSINESS_TZ", "Etc/UTC")

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
