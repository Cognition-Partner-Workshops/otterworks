from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
os.environ.setdefault("BILLING_SVC_MONGODB_URI", "mongodb://localhost:27017")
