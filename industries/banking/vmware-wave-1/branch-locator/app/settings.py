import os
from zoneinfo import ZoneInfo

DB_HOST = os.environ["DB_HOST"]
DB_NAME = os.environ["DB_NAME"]
DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]
DB_PORT = int(os.environ.get("DB_PORT", "5432"))
GEO_URL = os.environ["GEO_URL"]
BRANCH_TZ = ZoneInfo(os.environ["BRANCH_TZ"])
