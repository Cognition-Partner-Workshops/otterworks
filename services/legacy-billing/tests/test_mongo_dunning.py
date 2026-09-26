import sys
from datetime import datetime
from pathlib import Path

import pytest

pytest.importorskip("bson")
from bson.int64 import Int64

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from backends import mongo_dunning


def test_render_row():
    doc = {
        "_id": "80000000-0000-0000-0000-000000000001",
        "tenantId": "00000000-0000-0000-0000-000000000005",
        "invoiceId": "60000000-0000-0000-0000-000000000002",
        "attemptNo": Int64(1),
        "scheduledFor": datetime(2026, 2, 16),
        "statusCd": Int64(20),
        "status": "sent",
    }
    assert mongo_dunning.render_row(doc) == {
        "id": "80000000-0000-0000-0000-000000000001",
        "tenant_id": "00000000-0000-0000-0000-000000000005",
        "invoice_id": "60000000-0000-0000-0000-000000000002",
        "attempt_no": "1",
        "scheduled_for": "2026-02-16",
        "status": "sent",
    }
