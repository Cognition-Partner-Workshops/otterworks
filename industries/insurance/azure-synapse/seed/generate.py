"""Deterministic frozen-window extract for the policy and claims warehouse.

The CSVs in this folder are the frozen input both engines load. Re-running this
script reproduces them byte for byte.
"""
import csv
import datetime as dt
import random
from pathlib import Path

OUT = Path(__file__).parent
R = random.Random(20260930)
WINDOW = dt.date(2026, 9, 30)

REGIONS = [("NE", "Northeast"), ("SE", "Southeast"), ("MW", "Midwest"),
           ("SW", "Southwest"), ("NW", "Northwest"), ("PR", "Pacific Rim")]
QUIET_REGIONS = {"NW", "PR"}
FIRST = ["Ana", "Ben", "Chloe", "Dev", "Elena", "Femi", "Grace", "Hiro", "Isla", "Jon",
         "Kai", "Lena", "Mateo", "Nora", "Omar", "Priya", "Quinn", "Rosa", "Sam", "Tara"]
LAST = ["Abbott", "Baker", "Castillo", "Duarte", "Evans", "Fischer", "Gupta", "Hale",
        "Ibarra", "Jensen", "Kowalski", "Lindqvist", "Moreau", "Nakamura", "Okafor",
        "Patel", "Quintero", "Rossi", "Sato", "Thompson"]
AGENCIES = ["Harbor Point Agency", "Summit Risk Partners", "Lakeside Brokerage",
            "Granite Mutual Agents", "Bluewater Insurance Group", "Prairie Shield"]
PRODUCTS = ["AUTO", "HOME", "UMBR", "BOAT", "RENT"]
STATUSES = [("OPEN", "Open"), ("CLSD", "Closed"), ("REOP", "Reopened"),
            ("DENY", "Denied"), ("SUBR", "In subrogation")]
EVENT_TYPES = ["created", "assigned", "note_added", "reserve_change", "closed"]
ALT_LABELS = ["Work", "Mobile", "Spouse", "Assistant", None]


def write(name, header, rows):
    with open(OUT / f"{name}.csv", "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def main():
    write("dim_region", ["region_code", "region_name"], REGIONS)

    producers, tiers = [], []
    for i in range(60):
        code = f"P{1001 + i}"
        region = REGIONS[i % len(REGIONS)][0]
        producers.append([code, f"{R.choice(FIRST)} {R.choice(LAST)}", R.choice(AGENCIES), region])
        start = dt.date(2023, 1, 1) + dt.timedelta(days=R.randint(0, 600))
        tiers.append([code, "Bronze", start.isoformat()])
        tiers.append([code, "Silver", (start + dt.timedelta(days=R.randint(200, 500))).isoformat()])
        if i % 5 == 4:
            tiers.append([code, "Provisional", ""])
    write("dim_producer", ["producer_code", "producer_name", "agency_name", "region_code"], producers)
    write("producer_tier", ["producer_code", "tier_name", "tier_effective_date"], tiers)

    feed, fid = [], 1
    for d in (WINDOW - dt.timedelta(days=1), WINDOW):
        for code, _, _, region in producers:
            if region in QUIET_REGIONS and d == WINDOW:
                continue
            for _ in range(R.randint(1, 3)):
                pc = R.randint(5, 80)
                feed.append([fid, code.lower() if int(code[1:]) % 5 in (1, 2, 3) else code, region, pc,
                             R.randint(0, pc // 3), f"{R.uniform(1500, 90000):.2f}", d.isoformat()])
                fid += 1
    write("producer_feed", ["feed_id", "producer_code", "region_code", "policy_count",
                            "claim_count", "written_premium", "feed_date"], feed)

    policies = []
    for i in range(2000):
        label = R.choice(ALT_LABELS)
        alt = None
        if R.random() < 0.7:
            alt = f"+1 (555) {R.randint(100, 999)}-{R.randint(1000, 9999)}"
            if R.random() < 0.3:
                alt += f" ext {R.randint(10, 999)}"
        policies.append([f"PL{100000 + i:08d}"[:10], R.choice(FIRST),
                         R.choice(FIRST) if R.random() < 0.55 else "", R.choice(LAST),
                         R.choice(PRODUCTS), R.choice(REGIONS)[0],
                         f"555-{R.randint(100, 999)}-{R.randint(1000, 9999)}",
                         label or "", alt or ""])
    write("dim_policy", ["policy_number", "holder_first", "holder_middle", "holder_last",
                         "product_code", "region_code", "primary_phone", "alt_phone_label",
                         "alt_phone"], policies)
    write("claim_status_ref", ["status_code", "status_desc"], STATUSES)

    premium = []
    for p in R.sample(policies, 1500):
        premium.append([p[0].ljust(12), f"{R.uniform(300, 6000):.2f}",
                        (WINDOW - dt.timedelta(days=R.randint(0, 29))).isoformat()])
    write("premium_feed", ["policy_number", "premium_amount", "effective_date"], premium)

    claims = []
    for cid in range(1, 3001):
        p = R.choice(policies)[0]
        status = R.choice(STATUSES)[0]
        reopen = ""
        if status == "REOP":
            reopen = (WINDOW - dt.timedelta(days=R.randint(0, 20))).isoformat()
        claims.append([cid, p.lower() if R.random() < 0.5 else p, status, reopen,
                       f"{R.uniform(100, 25000):.2f}",
                       (WINDOW - dt.timedelta(days=R.randint(0, 29))).isoformat()])
    write("claim_feed", ["claim_id", "policy_number", "status_code", "reopen_date",
                         "claim_amount", "loss_date"], claims)

    def events(n, keys, seed_key):
        rows = []
        for eid in range(1, n + 1):
            ts = dt.datetime.combine(WINDOW, dt.time()) - dt.timedelta(
                seconds=R.randint(0, 29 * 86400), milliseconds=R.randint(0, 999))
            rows.append([eid, R.choice(keys), R.choice(EVENT_TYPES), ts.isoformat(sep=" ", timespec="milliseconds")])
        return rows
    write("claim_event", ["event_id", "claim_id", "event_type", "event_at"],
          events(5000, [c[0] for c in claims], "claim"))
    write("policy_event", ["event_id", "policy_number", "event_type", "event_at"],
          events(3000, [p[0] for p in policies], "policy"))


if __name__ == "__main__":
    main()
