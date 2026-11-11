#!/usr/bin/env python3
"""Generate pipe-delimited landing files for the local batch estate."""
import argparse
import csv
from contextlib import ExitStack
from datetime import date, timedelta
import hashlib
import json
import math
from pathlib import Path
import random
import sys

from generate_blobs import generate_blobs

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jobs" / "py"))
from common.schemas import DAILY_TABLES, DIMENSION_ROWS, SCHEMAS, TABLES


FIRST_NAMES = ("Mara", "Elias", "Nora", "Theo", "Iris", "Adrian", "Leila", "Owen", "Anika", "Jonah", "Sofia", "Malik", "Clara", "Felix", "Rina", "Hugo")
LAST_NAMES = ("Mercer", "Voss", "Calder", "Navarro", "Bennett", "Okafor", "Moreau", "Patel", "Sorensen", "Alvarez", "Reed", "Tanaka", "Costa", "Laurent", "Hale", "Adebayo")
COMPANY_ROOTS = ("Bramble", "Larkspur", "Cinderbrook", "Asterfold", "Copperfinch", "Fernhaven", "Morrowfield", "Willowmere", "Hazelcrest", "Ternvale", "Juniperwick", "Alderhaven")
COMPANY_LINES = ("Research", "Logistics", "Advisory", "Manufacturing", "Design", "Analytics", "Systems", "Foods", "Engineering", "Publishing", "Energy", "Materials")
TEAM_NAMES = ("Revenue Operations", "Platform Reliability", "Customer Success", "Financial Planning", "Product Research", "Design Studio", "Security Operations", "People Operations", "Legal Affairs", "Data Engineering", "Commercial Finance", "Quality Assurance")
REGIONS = (("USD", "US"), ("USD", "US"), ("USD", "US"), ("EUR", "DE"), ("EUR", "FR"), ("GBP", "GB"), ("CAD", "CA"), ("AUD", "AU"))
AGENTS = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36", "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 Version/17.6 Safari/605.1.15", "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0")
CHART = (
    ("1000", "Operating cash", "ASSET"), ("1010", "Cash in transit", "ASSET"),
    ("1100", "Trade receivables", "ASSET"), ("1150", "Unbilled revenue", "ASSET"),
    ("1200", "Prepaid services", "ASSET"), ("2000", "Trade payables", "LIABILITY"),
    ("2100", "Deferred subscription revenue", "LIABILITY"), ("2200", "Sales tax payable", "LIABILITY"),
    ("2300", "Accrued operating expenses", "LIABILITY"), ("3000", "Paid-in capital", "EQUITY"),
    ("3100", "Retained earnings", "EQUITY"), ("4000", "Subscription revenue", "REVENUE"),
    ("4100", "Usage revenue", "REVENUE"), ("4200", "Professional services revenue", "REVENUE"),
    ("4300", "Sales returns and allowances", "REVENUE"), ("4500", "Hosting expense", "EXPENSE"),
    ("4600", "Customer support expense", "EXPENSE"), ("4700", "Payment processing fees", "EXPENSE"),
    ("4800", "Office and administration", "EXPENSE"), ("4900", "Research and development", "EXPENSE"),
)


def person(i):
    return FIRST_NAMES[(i * 7) % len(FIRST_NAMES)], LAST_NAMES[(i // 7 + i * 3) % len(LAST_NAMES)]


def company(i):
    return COMPANY_ROOTS[(i * 7) % len(COMPANY_ROOTS)] + " " + COMPANY_LINES[(i // 12 + i * 5) % len(COMPANY_LINES)]


def user_emails(rows):
    occurrences = {}
    emails = {}
    for i in range(1, rows + 1):
        first, last = person(i)
        domain = company(i).lower().replace(" ", "-") + ".example"
        local = f"{first.lower()}.{last.lower()}"
        key = local, domain
        number = occurrences.get(key, 0) + 1
        occurrences[key] = number
        suffix = "" if number == 1 else str(number)
        emails[i] = f"{local}{suffix}@{domain}"
    return emails


def money(rng, median=240.0):
    return f"{max(0.01, rng.lognormvariate(math.log(median), 1.25)):.2f}"


def journal(i, rows, seed):
    number = (i + 1) // 2
    rng = random.Random(seed + number * 31)
    amount = money(rng)
    if rows % 2 and i == rows:
        amount = "0.00"
    source = ("INVOICE", "PAYMENT", "CREDIT_NOTE")[(number - 1) % 3]
    debit, credit = {"INVOICE": (3, 12), "PAYMENT": (1, 3), "CREDIT_NOTE": (15, 3)}[source]
    line = (i - 1) % 2 + 1
    return {
        "JOURNAL_ID": number, "LINE_NO": line,
        "GL_ACCOUNT_ID": min(debit if line == 1 else credit, max(1, min(rows, 20))),
        "DEBIT_AMT": amount if line == 1 else "0.00",
        "CREDIT_AMT": amount if line == 2 else "0.00",
        "CURRENCY_CODE": REGIONS[number % len(REGIONS)][0],
        "POSTING_DATE": date(2026, 1, 1) + timedelta(days=number % 313),
        "SOURCE": source, "CUSTOMER_ID": number, "INVOICE_ID": number,
    }


def record(table, i, day, rows, rng, seed, blobs=None, emails=None):
    if table == "GL_ACCOUNT":
        code, label, kind = CHART[i - 1]
        return {"GL_ACCOUNT_ID": i, "ACCOUNT_CODE": code, "ACCOUNT_NAME": label, "ACCOUNT_TYPE": kind}
    if table == "GL_JOURNAL_LINE":
        return {"GL_JOURNAL_LINE_ID": i, **journal(i, rows, seed)}
    if table == "FILE_OBJECT":
        return {"FILE_OBJECT_ID": i, "DOCUMENT_ID": i, **blobs[(i - 1) % len(blobs)]}
    first, last = person(i)
    email = emails[i]
    currency, country = REGIONS[i % len(REGIONS)]
    business_date = day if table in DAILY_TABLES else date(2026, 1, 1) + timedelta(days=(i * 13) % 313)
    timestamp = f"{business_date} {i % 24:02}:{i % 60:02}:{(i // 60) % 60:02}"
    event_type = ("document.read", "document.update", "document.share", "user.login", "billing.invoice.created")[i % 5]
    actor = None if table == "AUDIT_EVENT" and rng.random() < 0.3 else i
    if table == "AUDIT_EVENT" and actor is None:
        event_type = "system.index.refresh"
    amounts = {
        "TOTAL_AMOUNT": money(rng), "AMOUNT": money(rng),
        "UNIT_PRICE": money(rng, 45), "MONTHLY_PRICE": money(rng, 89),
        "RATE": ("0.0000", "0.0500", "0.0700", "0.0850", "0.1000", "0.1900", "0.2000", "0.2100")[i % 8],
        "SCORE": f"{min(100, max(0, rng.gauss(35, 17))):.2f}",
    }
    names = {
        "ACCOUNT_NUMBER": f"ACC-{i + 41000:07}",
        "INVOICE_NUMBER": f"INV-2026-{i + 12000:07}",
        "ACCOUNT_NAME": company(i), "DISPLAY_NAME": f"{first} {last}",
        "EMAIL": email, "CURRENCY_CODE": currency, "COUNTRY": country,
        "PLAN_NAME": ("Starter", "Team", "Business", "Enterprise")[i % 4] + (" Monthly", " Annual", " Flex")[i % 3],
        "REGION": country, "DEPARTMENT": TEAM_NAMES[i % len(TEAM_NAMES)],
        "TEAM_NAME": TEAM_NAMES[i % len(TEAM_NAMES)] + ("", " EMEA", " Americas", " APAC", " Core", " Enablement")[(i // len(TEAM_NAMES)) % 6],
        "FOLDER_NAME": ("Board materials", "Vendor contracts", "Customer onboarding", "Product specifications", "Monthly close", "Policy library")[i % 6],
        "TITLE": ("Quarterly operating review", "Services agreement", "Architecture decision record", "Revenue forecast", "Access certification", "Launch readiness checklist")[i % 6] + f" - {business_date:%b %Y}",
        "ROLE": ("member", "editor", "reviewer", "administrator")[i % 4],
        "PERMISSION": ("view", "comment", "edit")[i % 3],
        "PROVIDER": ("saml", "oidc", "directory")[i % 3],
        "EXTERNAL_ID": hashlib.sha256(email.encode()).hexdigest()[:32],
        "SESSION_ID": hashlib.sha256(f"{email}:{business_date}".encode()).hexdigest()[:24],
        "OBJECT_KEY": f"documents/{business_date:%Y/%m}/{hashlib.sha256(str(i).encode()).hexdigest()[:20]}.pdf",
        "CHECKSUM": hashlib.sha256(str(i).encode()).hexdigest(),
        "IP_ADDRESS": f"192.0.2.{i % 254 + 1}",
        "USER_AGENT": AGENTS[i % len(AGENTS)],
        "EVENT_TYPE": event_type,
        "REASON": ("Prorated plan change", "Service availability credit", "Annual contract discount", "Billing address correction")[i % 4],
        "TAG": (" Finance ", "REPORT", " annual  review ", "Ops", "customer-contract")[i % 5],
        "POLICY_NAME": ("Financial records", "User activity", "Contract archive", "Operational logs", "Customer exports", "Legal correspondence")[i % 6],
        "FLAG_TYPE": ("retention.expired", "external.share", "sensitive.content", "review.overdue")[i % 4],
        "ALERT_TYPE": ("unusual.download.volume", "new.location.login", "permission.escalation", "repeated.authentication.failure")[i % 4],
        "BODY": f"{first} {last} reviewed the {company(i)} operating plan. Revision {(i - 1) % 3 + 1}: confirm the service schedule, reconcile usage charges, and obtain finance approval before {business_date:%d %B %Y}.",
        "DETAILS": json.dumps({"resource": f"document/{i}", "operation": event_type, "result": "success", "origin": "scheduler" if actor is None else "web"}),
        "PREF_JSON": json.dumps({"theme": "dark" if i % 2 else "light", "notifications": {"email": bool(i % 3), "digest": "weekly"}, "locale": ("en-US", "en-GB", "fr-FR", "de-DE")[i % 4], "timezone": ("America/New_York", "Europe/London", "Europe/Paris", "Europe/Berlin")[i % 4]}),
    }
    names["RAW_LINE"] = f'{business_date}T12:00:00Z level=INFO actor={email} document={i} action={"login" if table == "LOGIN_EVENT" else "index"} status=200 ip={names["IP_ADDRESS"]} agent="{names["USER_AGENT"]}"'
    statuses = {
        "CUSTOMER_ACCOUNT": ("active", "active", "active", "suspended"),
        "APP_USER": ("active", "active", "invited", "disabled"),
        "SUBSCRIPTION": ("active", "active", "trialing", "closed"),
        "INVOICE_HDR": ("paid", "paid", "open", "overdue"),
        "PAYMENT": ("settled", "settled", "pending", "failed"),
        "DOCUMENT": ("published", "draft", "published", "archived"),
    }
    choices = statuses.get(table, ("active", "pending", "closed"))
    names["STATUS"] = choices[i % len(choices)]
    integer_values = {
        "PARENT_FOLDER_ID": None if i == 1 else i // 2,
        "PLAN_ID": (i - 1) % max(1, min(rows, 12)) + 1,
        "TEAM_ID": (i - 1) // 5 + 1,
        "SHARED_WITH_USER_ID": ((i - 1) // 5 * 5 + i % 5) % max(rows, 1) + 1,
        "ACTOR_USER_ID": actor, "VERSION_NUMBER": (i - 1) % 3 + 1,
        "SIZE_BYTES": int(rng.lognormvariate(12, 1.4)), "QUANTITY": rng.randint(1, 12),
        "UNITS": rng.randint(10, 10000), "LOGIN_COUNT": rng.randint(1, 24),
        "ACTION_COUNT": rng.randint(1, 450), "DOCUMENT_COUNT": rng.randint(1, 250),
        "RETENTION_DAYS": (30, 90, 365, 730, 1825, 2555)[i % 6],
        "SEVERITY": rng.randint(1, 10000), "EVENT_COUNT": rng.randint(100, 100000),
        "SOURCE_COUNT": 25000 + i % 500, "TARGET_COUNT": 25000 + i % 500,
        "GL_ACCOUNT_ID": min(15, max(1, min(rows, 20))),
    }
    if table == "DOCUMENT":
        integer_values.update(OWNER_USER_ID=(i - 1) // 4 + 1, FOLDER_ID=(i - 1) // 8 + 1)
    if table == "DOC_VERSION":
        integer_values["DOCUMENT_ID"] = (i - 1) // 3 + 1
    result = {}
    for name, kind in SCHEMAS[table]:
        if name == SCHEMAS[table][0][0]:
            result[name] = i
        elif name in integer_values:
            result[name] = integer_values[name]
        elif kind == "BIGINT" and name.endswith("_ID"):
            result[name] = i
        elif kind == "DATE":
            result[name] = business_date + timedelta(days=30) if name == "DUE_DATE" else business_date
        elif kind == "TIMESTAMP":
            result[name] = timestamp
        elif name in amounts:
            result[name] = amounts[name]
        else:
            result[name] = names[name]
    return result


def generate(output, rows, seed):
    if rows < 0:
        raise ValueError("rows must be nonnegative")
    rng = random.Random(seed)
    blobs = generate_blobs(output, rows, seed)
    emails = user_emails(rows)
    for area, tables in TABLES.items():
        for table in tables:
            folder = output / area / table
            folder.mkdir(parents=True, exist_ok=True)
            for old in folder.glob("*.psv"):
                old.unlink()
            days = [date(2026, 11, 9) - timedelta(days=d) for d in range(6, -1, -1)] if table in DAILY_TABLES else [date(2026, 11, 9)]
            count = min(rows, DIMENSION_ROWS.get(table, rows))
            with ExitStack() as stack:
                writers = [csv.writer(stack.enter_context((folder / f"{day:%Y%m%d}.psv").open("w", newline="")), delimiter="|", lineterminator="\n") for day in days]
                for writer in writers:
                    writer.writerow([name for name, _ in SCHEMAS[table]])
                for i in range(1, count + 1):
                    slot = (i - 1) % len(days)
                    row = record(table, i, days[slot], rows, rng, seed, blobs, emails)
                    writers[slot].writerow([row[name] for name, _ in SCHEMAS[table]])
            print(f"{area}.{table}: {count}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=200000)
    parser.add_argument("--seed", type=int, default=1110)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / ".data" / "landing")
    args = parser.parse_args()
    generate(args.output, args.rows, args.seed)
