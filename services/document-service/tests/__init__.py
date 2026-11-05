"""Test package.

Settings require DOC_SVC_DATABASE_URL; give the suite a credential-free URL
before app.config is imported. Tests use their own SQLite engine and never
connect to it.
"""

import os

os.environ.setdefault("DOC_SVC_DATABASE_URL", "postgresql+asyncpg://test@localhost:5432/test")
