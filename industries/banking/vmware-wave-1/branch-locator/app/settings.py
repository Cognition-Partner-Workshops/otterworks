# Settings for branch-locator on web-02.
import os

DB_HOST = "wave1-db"
DB_NAME = "bankwave"
DB_USER = "branch_app"
DB_PASSWORD = os.environ.get("BRANCH_LOCATOR_DB_PASSWORD")
if not DB_PASSWORD:
    raise RuntimeError("BRANCH_LOCATOR_DB_PASSWORD must be set and non-empty")

GEO_URL = "http://geo.bank.internal:8090/geocode"

TEMPLATE_DIR = "/opt/branch-locator/app/templates"
LOG_FILE = "/var/log/branch-locator/app.log"

PORT = 5000
