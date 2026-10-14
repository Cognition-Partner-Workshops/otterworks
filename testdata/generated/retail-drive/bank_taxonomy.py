"""Fictional Bank of America concept-demo drive taxonomy."""
from __future__ import annotations

YEARS = [2024, 2025, 2026]
QUARTERS = ["Q1", "Q2", "Q3", "Q4"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
REGIONS = ["Northeast", "Mid-Atlantic", "Southeast", "Midwest", "Southwest", "West"]
CLIENTS = [
    "Harborview Logistics LLC",
    "Summit Orchard Holdings Inc",
    "Copperline Renewable Energy Co",
    "Bluehaven Medical Supply Ltd",
    "Northstar Freightworks LLC",
    "Cedar Ridge Fabrication Inc",
    "Meridian Arts and Education Foundation",
    "Silverfern Data Systems LLC",
    "Redwood Robotics Group",
    "Lakeshore Community Foods Co-op",
    "Brightwater Industrial Design LLC",
    "Moonstone Property Services Inc",
]
LOANS = [
    "LN-2024-100231", "LN-2024-100232", "LN-2024-100233", "LN-2024-100234",
    "LN-2025-101241", "LN-2025-101242", "LN-2025-101243", "LN-2025-101244",
    "LN-2026-102251", "LN-2026-102252", "LN-2026-102253", "LN-2026-102254",
]
PRODUCTS = [
    "Checking", "Savings", "Mortgage", "HELOC", "Auto Loan", "Credit Card",
    "SBA 7(a)", "Treasury Mgmt",
]

AXES = {
    "year": YEARS,
    "quarter": QUARTERS,
    "month": MONTHS,
    "region": REGIONS,
    "client": CLIENTS,
    "loan": LOANS,
    "product": PRODUCTS,
}

# Axis breadth at scale 1.0; selected() further scales each axis consistently.
AXIS_BASE = {
    "year": 3,
    "quarter": 4,
    "month": 2,
    "region": 6,
    "client": 12,
    "loan": 12,
    "product": 8,
}


def _s(folder, name, type, expand=None, kind=None):
    spec = {"folder": folder, "name": name, "type": type, "expand": expand or []}
    if kind:
        spec["kind"] = kind
    return spec


DEPARTMENTS: dict[str, list[dict]] = {
    "Consumer Lending": [
        _s("Loan Applications", "{loan} Application Packet", "pdf", ["loan"]),
        _s("Credit Decisions", "{loan} Credit Memo", "docx", ["loan"]),
        _s("Servicing/Payment Histories", "{loan} Payment History {year}", "xlsx", ["loan", "year"]),
        _s("Rates", "{product} Rate Sheet {year}", "csv", ["product", "year"]),
        _s("Portfolio/Quarterly Reviews", "{quarter} {year} Delinquency Review", "xlsx", ["quarter", "year"]),
        _s("Portfolio/Charts", "{quarter} {year} Consumer Lending Portfolio", "png",
           ["quarter", "year"], kind="chart"),
    ],
    "Commercial Banking": [
        _s("Client Onboarding/KYC", "{client} KYC Checklist", "docx", ["client"]),
        _s("Client Onboarding/Ownership", "{client} Beneficial Ownership Form", "pdf", ["client"]),
        _s("Credit Reviews", "{client} Credit Review {year}", "docx", ["client", "year"]),
        _s("Portfolio/Quarterly", "{quarter} {year} Commercial Exposure Report", "xlsx",
           ["quarter", "year"]),
        _s("Treasury Services/Onboarding", "{client} Cash Management Enrollment", "pdf", ["client"]),
        _s("Deposits/Activity", "{region} Commercial Deposit Activity {year}", "csv",
           ["region", "year"]),
    ],
    "Wealth Management": [
        _s("Client Profiles", "{client} Investment Profile", "docx", ["client"]),
        _s("Client Suitability", "{client} Suitability Checklist {year}", "pdf",
           ["client", "year"]),
        _s("Portfolio/Quarterly", "{quarter} {year} Portfolio Review", "xlsx", ["quarter", "year"]),
        _s("Portfolio/Charts", "{quarter} {year} Portfolio Allocation", "png",
           ["quarter", "year"], kind="chart"),
        _s("Statements/Monthly", "{month} {year} Wealth Account Statement", "pdf",
           ["month", "year"]),
        _s("Product Disclosures", "{product} Disclosure {year}", "docx", ["product", "year"]),
    ],
    "Risk & Compliance": [
        _s("Due Diligence/CDD", "{client} CDD Checklist", "docx", ["client"]),
        _s("Credit Risk/Quarterly", "{region} {quarter} {year} Credit Risk Report", "xlsx",
           ["region", "quarter", "year"]),
        _s("Credit Risk/Charts", "{quarter} {year} Credit Risk Trend", "png",
           ["quarter", "year"], kind="chart"),
        _s("AML/SAR Policies", "AML and SAR Policy {year}", "pdf", ["year"]),
        _s("BSA Training", "BSA Training Deck {year}", "pptx", ["year"]),
        _s("SAR Case Index", "{region} SAR Case Index {year}", "csv", ["region", "year"]),
        _s("Controls/Testing", "{quarter} {year} Compliance Control Review", "md",
           ["quarter", "year"]),
    ],
    "Treasury": [
        _s("Liquidity/LCR", "{month} {year} Liquidity Coverage Ratio Report", "xlsx",
           ["month", "year"]),
        _s("Liquidity/Quarterly LCR", "{quarter} {year} Liquidity Coverage Ratio Review",
           "pdf", ["quarter", "year"]),
        _s("Liquidity/Quarterly", "{quarter} {year} Liquidity Forecast", "pdf",
           ["quarter", "year"]),
        _s("Cash Forecasts", "{region} Cash Forecast {year}", "csv", ["region", "year"]),
        _s("Rates", "{product} Treasury Rate Sheet {year}", "csv", ["product", "year"]),
        _s("Policies", "Funding Contingency Procedure", "md"),
    ],
    "Operations": [
        _s("Account Statements/Monthly", "{month} {year} Account Statement", "pdf",
           ["month", "year"]),
        _s("Branch Procedures", "{region} Branch Operations Procedure", "docx", ["region"]),
        _s("Payments/Reconciliation", "{month} {year} Payment Reconciliation", "xlsx",
           ["month", "year"]),
        _s("Payments/Controls", "{quarter} {year} Wire Transfer Control Review", "pdf",
           ["quarter", "year"]),
        _s("Exceptions", "{region} Operations Exception Log", "csv", ["region"]),
    ],
    "Human Resources": [
        _s("Policies", "People Operations Handbook {year}", "pdf", ["year"]),
        _s("Training", "{quarter} {year} Conduct and Privacy Training", "pptx",
           ["quarter", "year"]),
        _s("Workforce Planning", "{region} Workforce Plan {year}", "xlsx",
           ["region", "year"]),
        _s("Role Guides", "Branch Operations Role Guide", "docx"),
        _s("Role Guides", "Client Service Role Guide", "docx"),
        _s("Role Guides", "Risk Review Role Guide", "docx"),
        _s("Role Guides", "Treasury Services Role Guide", "docx"),
    ],
    "Technology": [
        _s("Runbooks", "Technology Incident Response Runbook", "md"),
        _s("Security/Access Reviews", "{region} Access Review {year}", "xlsx",
           ["region", "year"]),
        _s("Change Management", "{quarter} {year} Change Calendar", "csv",
           ["quarter", "year"]),
        _s("Service Continuity", "{region} Service Continuity Test {year}", "pdf",
           ["region", "year"]),
        _s("Security/Assessments", "{year} Security Control Assessment", "docx", ["year"]),
    ],
}

ASSET_PLACEMENTS: list[tuple[str, tuple[str, ...]]] = []

DEPARTMENT_DOCS: dict[str, list[str]] = {
    "Consumer Lending": [
        "Credit Policy Summary",
        "Loan Origination Checklist",
        "Underwriting Standards",
        "Servicing Quality Review",
    ],
    "Commercial Banking": [
        "Client Onboarding Standard",
        "Commercial Credit Framework",
        "Treasury Services Guide",
        "Portfolio Monitoring Summary",
    ],
    "Wealth Management": [
        "Investment Governance Summary",
        "Client Suitability Framework",
        "Quarterly Allocation Brief",
        "Fiduciary Operations Guide",
    ],
    "Risk & Compliance": [
        "Enterprise Risk Overview",
        "Anti-Money Laundering Policy",
        "Suspicious Activity Escalation Guide",
        "BSA Compliance Training Guide",
    ],
    "Treasury": [
        "Liquidity Risk Framework",
        "Liquidity Coverage Ratio Overview",
        "Funding Contingency Playbook",
        "Cash Forecasting Method",
    ],
    "Operations": [
        "Branch Operations Standard",
        "Payment Reconciliation Guide",
        "Account Servicing Procedures",
        "Records Retention Guide",
    ],
    "Human Resources": [
        "People Operations Handbook",
        "Workforce Planning Summary",
        "Learning and Development Guide",
        "Privacy and Conduct Standard",
    ],
    "Technology": [
        "Security Operations Overview",
        "Incident Response Runbook",
        "Service Continuity Standard",
        "Access Governance Guide",
    ],
}


def all_departments() -> list[str]:
    return list(DEPARTMENTS)
