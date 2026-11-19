import hashlib
import json
import os
import uuid
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from decimal import Decimal


@dataclass(frozen=True)
class Settings:
    seed: str = "1795112287"
    db2_customers: int = 50000
    db2_history: int = 400000
    oracle_accounts: int = 40000
    pg_contacts: int = 30000
    dup_rate: float = 0.02

    def __post_init__(self):
        if min(self.db2_customers, self.db2_history, self.oracle_accounts, self.pg_contacts) < 0:
            raise ValueError("Row counts must be nonnegative")
        if self.db2_history and not self.db2_customers:
            raise ValueError("History requires customers")
        if not 0 <= self.dup_rate <= 0.25:
            raise ValueError("Rate must be between zero and 0.25")

    @classmethod
    def environment(cls):
        defaults = cls()
        return cls(**{k: type(v)(os.getenv("ODL_" + k.upper(), v)) for k, v in asdict(defaults).items()})

    @property
    def version(self):
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()

    @property
    def shared_count(self):
        return min(self.db2_customers, self.oracle_accounts, self.pg_contacts)

    @property
    def branch_count(self):
        return int(self.shared_count * self.dup_rate)


def number(settings, purpose, index):
    return int.from_bytes(hashlib.sha256(f"{settings.seed}:{purpose}:{index}".encode()).digest()[:8], "big")


def person(settings, index, office="central"):
    first = ("Alex", "Morgan", "Sam", "Robin", "Taylor", "Jordan", "Casey", "Drew")
    last = ("Rivera", "Martin", "Lee", "Wilson", "Patel", "Baker", "Young", "Clark")
    n = number(settings, "customer", index)
    name = f"{first[n % 8]} {last[(n // 8) % 8]} {index:06d}"
    if index % 100 == 0:
        name = f"José García {index:06d}"
    address = f"{10 + n % 9000} Cedar Road, Suite {index % 200}"
    if office == "regional":
        name = f"{last[(n // 8) % 8]}, {first[n % 8][0]}. {index:06d}"
        address = f"{20 + n % 7000} Oak Avenue, Unit {index % 80}"
    return name, address


def customer_no(index):
    return f"C{index + 1:07d}  "


def contact_id(settings, index):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"otterworks:{settings.seed}:crm:{index}"))


def customers(settings):
    for i in range(settings.db2_customers):
        name, address = person(settings, i)
        stored = name.encode("utf-8")
        if i % 100 == 0:
            name = f"José García {i:06d}"
            stored = name.encode("cp037")
        opened = "0001-01-01" if i % 100 == 0 else str(date(2010, 1, 1) + timedelta(days=i % 4000))
        yield {"cust_no": customer_no(i), "full_name": stored.hex(), "address": address,
               "opened_on": opened, "opened_ymd": int(opened.replace("-", ""))}


def history(settings):
    for i in range(settings.db2_history):
        yield {"history_id": i + 1, "cust_no": customer_no(i % settings.db2_customers),
               "event_on": str(date(2020, 1, 1) + timedelta(days=i % 1460)),
               "amount": str(Decimal(number(settings, "history", i) % 1000000) / 100)}


def products():
    for i, name in enumerate(("Everyday", "Savings", "Business", "Premium"), 1):
        yield {"product_id": i, "name": name}


def accounts(settings):
    times = ("2024-03-10 01:55:00", "2024-03-10 03:05:00", "2024-11-03 01:15:00", "2024-11-03 01:45:00")
    for i in range(settings.oracle_accounts):
        name, address = person(settings, i, "regional" if i < settings.branch_count else "central")
        opened = times[i] if i < len(times) else f"2024-01-{1 + i % 28:02d} 14:35:20"
        yield {"account_id": 7000000 + i * 17, "holder_name": name, "address": address,
               "product_id": 1 + i % 4, "balance": format(Decimal(number(settings, "balance", i) % 100000000) / 100, ".2f"),
               "opened_at": opened}


def contacts(settings):
    for i in range(settings.branch_count, settings.branch_count + settings.pg_contacts):
        name, address = person(settings, i)
        yield {"contact_id": contact_id(settings, i), "full_name": name, "address": address,
               "credit": 0.1 + 0.2 if (i - settings.branch_count) % 50 == 0 else (i % 10000) / 100}


def cases(settings):
    for i in range(settings.pg_contacts * 2):
        identity = settings.branch_count + i // 2
        yield {"case_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{settings.seed}:case:{i}")),
               "contact_id": contact_id(settings, identity), "subject": "Account statement request",
               "opened_at": "2024-11-04 09:30:00"}


def subscriptions(settings):
    for row in contacts(settings):
        yield {"contact_id": row["contact_id"], "status": "active"}


def records(settings):
    for table, rows in (("CUSTMAST", customers(settings)), ("ACCTHIST", history(settings)),
                        ("PRODUCTS", products()), ("ACCOUNTS", accounts(settings)),
                        ("contacts", contacts(settings)), ("service_cases", cases(settings)),
                        ("subscription_snapshots", subscriptions(settings))):
        for row in rows:
            yield json.dumps({"table": table, "row": row}, sort_keys=True, ensure_ascii=True, separators=(",", ":")) + "\n"
