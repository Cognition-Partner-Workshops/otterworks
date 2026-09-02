import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
import recon_u6


def test_extract_supports_contract_json_paths():
    payload = {"plan_code": "STARTER", "plans": [{"code": "STARTER"}]}
    assert recon_u6.extract(payload, "$.plan_code") == "STARTER"
    assert recon_u6.extract(payload["plans"], "$[*].code") == ["STARTER"]


def test_plans_001_response_matches_transcript():
    operation = recon_u6._operations()[0]
    response = [
        {"code": "STARTER", "monthly_fee": "49.00"},
        {"code": "GROWTH", "monthly_fee": "149.00"},
        {"code": "SCALE", "monthly_fee": "499.00"},
    ]
    assert recon_u6.flatten(
        recon_u6.extract_response(operation, response)
    ) == recon_u6.flatten(operation["expected"])


def test_plans_004_response_matches_transcript():
    operation = recon_u6._operations()[3]
    response = {
        "subscriptions": [
            {
                "ends_on": "2026-02-28",
                "plan_id": "10000000-0000-0000-0000-000000000001",
                "starts_on": "2026-01-01",
                "status": "active",
            },
            {
                "ends_on": None,
                "plan_id": "10000000-0000-0000-0000-000000000002",
                "starts_on": "2026-03-01",
                "status": "active",
            },
        ]
    }
    actual = recon_u6.extract_response(operation, response)
    assert recon_u6.flatten(actual) == recon_u6.flatten(operation["expected"])
