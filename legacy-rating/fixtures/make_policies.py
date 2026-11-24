#!/usr/bin/env python3
"""Generate the deterministic rating fixture: 200 policies in the POLREC layout.

The first block is hand-placed so every class, territory, override, eligibility
row and date boundary in ../tables is exercised at least once. The rest is drawn
from a fixed seed. Running this twice produces byte-identical output.

    python3 make_policies.py            # writes policies.dat
    python3 make_policies.py --check    # fails if policies.dat is stale
"""
import argparse
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "policies.dat"
COUNT = 200
SEED = 20261124

POS = "{ABCDEFGHI"
NEG = "}JKLMNOPQR"

CLASSES = {
    "GL": ["91340", "91580", "41650", "18501", "91111"],
    "PR": ["0311", "0702", "0900", "0567"],
    "CA": ["7398", "7219", "7911"],
}
TERRS = {
    "GL": ["000", "010", "020", "040", "099"],
    "PR": ["000", "010", "030", "040", "060"],
    "CA": ["000", "020", "050"],
}
STATES = ["CA", "TX", "NY", "IL", "FL"]


def overpunch(value_cents: int, digits: int) -> str:
    """Zoned decimal with the sign carried in the last digit (EBCDIC overpunch)."""
    text = f"{abs(value_cents):0{digits}d}"
    if len(text) > digits:
        raise ValueError(f"{value_cents} does not fit in {digits} digits")
    table = NEG if value_cents < 0 else POS
    return text[:-1] + table[int(text[-1])]


def record(p: dict) -> str:
    rec = (
        f"{p['id']:<8}"
        f"{p['line']:<2}"
        f"{p['state']:<2}"
        f"{p['cls']:<5}"
        f"{p['terr']:<3}"
        f"{p['eff']:<8}"
        f"{overpunch(p['exposure'], 9)}"
        f"{p['years']:02d}"
        f"{p['claims']:02d}"
        f"{p['deduct']:05d}"
        f"{p['multi']}"
        f"{overpunch(p['sched'], 3)}"
        f"{p['addl']:02d}"
        f"{p['equip']}{p['waiver']}{p['hnoa']}"
    )
    return rec.ljust(80)


def base(**kw) -> dict:
    p = dict(state="IL", eff="20260315", exposure=25000, years=5, claims=1,
             deduct=500, multi="N", sched=0, addl=0, equip="N", waiver="N", hnoa="N")
    p.update(kw)
    return p


def placed() -> list[dict]:
    rows = []
    # every class at least once, default territory
    for line, classes in CLASSES.items():
        for cls in classes:
            exp = {"GL": 21000, "PR": 150000, "CA": 300}[line]
            rows.append(base(line=line, cls=cls, terr="000", exposure=exp))
    rows.append(base(line="WC", cls="8810", terr="000", exposure=50000))
    # every territory, including an unknown one and an expired one
    for line, terrs in TERRS.items():
        cls = CLASSES[line][0]
        for terr in terrs:
            exp = {"GL": 18000, "PR": 120000, "CA": 200}[line]
            rows.append(base(line=line, cls=cls, terr=terr, exposure=exp, state="TX"))
    # territory 040 and class 41650 change on 1 July
    for eff in ("20260630", "20260701"):
        rows.append(base(line="GL", cls="91340", terr="040", eff=eff, exposure=30000))
        rows.append(base(line="GL", cls="41650", terr="010", eff=eff, exposure=40000))
    # overrides: inside, on the boundary, outside, and the same class elsewhere
    rows.append(base(line="GL", cls="91580", terr="040", eff="20260410", exposure=15050))
    rows.append(base(line="GL", cls="91580", terr="040", eff="20261231", exposure=15050))
    rows.append(base(line="GL", cls="91580", terr="020", eff="20260410", exposure=15050))
    rows.append(base(line="PR", cls="0702", terr="030", eff="20260228", exposure=410000))
    rows.append(base(line="PR", cls="0702", terr="030", eff="20260301", exposure=410000))
    rows.append(base(line="PR", cls="0702", terr="040", eff="20260601", exposure=410000))
    rows.append(base(line="CA", cls="7219", terr="020", eff="20260930", exposure=400))
    rows.append(base(line="CA", cls="7219", terr="020", eff="20261001", exposure=400))
    rows.append(base(line="CA", cls="7219", terr="050", eff="20260501", exposure=400))
    # eligibility keyed by class and state
    rows.append(base(line="CA", cls="7219", terr="000", state="NY", exposure=300))
    rows.append(base(line="CA", cls="7219", terr="000", state="IL", exposure=300))
    rows.append(base(line="CA", cls="7911", terr="000", state="NY", exposure=300))
    # exposure sign: negative and zero
    rows.append(base(line="GL", cls="18501", terr="000", exposure=-12500))
    rows.append(base(line="PR", cls="0311", terr="000", exposure=0))
    # experience: clean and seasoned, clean but new, three claims
    rows.append(base(line="GL", cls="91340", terr="010", claims=0, years=3, exposure=22000))
    rows.append(base(line="GL", cls="91340", terr="010", claims=0, years=2, exposure=22000))
    rows.append(base(line="GL", cls="91340", terr="010", claims=3, years=9, exposure=22000))
    # deductible bands on property and auto, and on liability where they do not apply
    for ded in (999, 1000, 2500, 5000):
        rows.append(base(line="PR", cls="0900", terr="010", deduct=ded, exposure=90000))
    rows.append(base(line="CA", cls="7398", terr="050", deduct=5000, exposure=300))
    rows.append(base(line="GL", cls="18501", terr="020", deduct=5000, exposure=60000))
    # schedule modification inside and beyond the 25 percent band
    for sched in (-30, -25, 15, 40):
        rows.append(base(line="GL", cls="91340", terr="020", sched=sched, exposure=16000))
    # multi-policy discount on each line
    for line, cls in (("GL", "18501"), ("PR", "0311"), ("CA", "7911")):
        exp = {"GL": 80000, "PR": 200000, "CA": 300}[line]
        rows.append(base(line=line, cls=cls, terr="000", multi="Y", exposure=exp))
    # minimum premium: state rows, default rows, and credits that land below
    rows.append(base(line="GL", cls="18501", terr="000", state="CA", exposure=40000))
    rows.append(base(line="GL", cls="18501", terr="000", state="IL", exposure=40000))
    rows.append(base(line="CA", cls="7911", terr="050", state="TX", exposure=200))
    rows.append(base(line="PR", cls="0311", terr="010", state="FL", exposure=80000))
    rows.append(base(line="GL", cls="18501", terr="010", exposure=50500, sched=-20, multi="Y"))
    rows.append(base(line="PR", cls="0311", terr="000", exposure=95000, sched=-15, multi="Y", claims=0, years=6))
    rows.append(base(line="GL", cls="18501", terr="000", exposure=42000, sched=20))
    # endorsements
    rows.append(base(line="GL", cls="91340", terr="000", addl=2, waiver="Y", exposure=30000))
    rows.append(base(line="GL", cls="91340", terr="000", addl=5, hnoa="Y", exposure=30000))
    rows.append(base(line="PR", cls="0702", terr="000", equip="Y", exposure=50000))
    rows.append(base(line="PR", cls="0702", terr="000", equip="Y", exposure=800000))
    rows.append(base(line="CA", cls="7398", terr="000", waiver="Y", hnoa="Y", exposure=500))
    rows.append(base(line="GL", cls="18501", terr="000", addl=3, waiver="Y", hnoa="Y", equip="Y", exposure=46000))
    return rows


def drawn(rng: random.Random, n: int) -> list[dict]:
    rows = []
    for _ in range(n):
        line = rng.choice(["GL", "GL", "PR", "PR", "CA"])
        cls = rng.choice(CLASSES[line][:-1] if line != "CA" else CLASSES[line])
        terr = rng.choice(TERRS[line])
        month = rng.randint(1, 12)
        day = rng.randint(1, 28)
        if line == "GL":
            exposure = rng.randint(8000, 260000)
        elif line == "PR":
            exposure = rng.randint(60000, 1200000)
        else:
            exposure = rng.randint(1, 14) * 100
        rows.append(base(
            line=line, cls=cls, terr=terr, state=rng.choice(STATES),
            eff=f"2026{month:02d}{day:02d}", exposure=exposure,
            years=rng.randint(0, 20), claims=rng.choice([0, 0, 0, 1, 1, 2, 3, 4]),
            deduct=rng.choice([250, 500, 1000, 2500, 5000]),
            multi=rng.choice("NNY"), sched=rng.choice([0, 0, -10, -5, 5, 10, -20, 25]),
            addl=rng.choice([0, 0, 1, 2, 4]) if line == "GL" else 0,
            equip=rng.choice("NNY") if line == "PR" else "N",
            waiver=rng.choice("NNY") if line in ("GL", "CA") else "N",
            hnoa=rng.choice("NY") if line == "GL" else "N",
        ))
    return rows


def build() -> str:
    rng = random.Random(SEED)
    rows = placed()
    rows += drawn(rng, COUNT - len(rows))
    out = []
    for i, p in enumerate(rows, start=1):
        p["id"] = f"P{i:07d}"
        out.append(record(p))
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    text = build()
    if args.check:
        if OUT.read_text() != text:
            print("policies.dat is stale; run make_policies.py", file=sys.stderr)
            return 1
        print(f"policies.dat OK ({text.count(chr(10))} policies)")
        return 0
    OUT.write_text(text)
    print(f"wrote {OUT.name} ({text.count(chr(10))} policies)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
