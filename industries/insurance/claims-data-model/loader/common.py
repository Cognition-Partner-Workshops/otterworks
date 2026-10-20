"""Shared helpers: connections, corpus paths and the two rounding rules the claims hub uses."""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal
from pathlib import Path

CENT = Decimal("0.01")


def corpus_dir() -> Path:
    path = Path(os.environ["CORPUS_DIR"])
    if not (path / "inputs" / "fnol").is_dir():
        raise SystemExit(f"claims hub corpus not found under {path}; run make corpus")
    return path


def pg_dsn() -> str:
    return os.environ["PG_DSN"]


def oracle_connect(user: str = "commission_pay"):
    import oracledb

    oracledb.defaults.fetch_decimals = True
    return oracledb.connect(user=user, password=user, dsn=os.environ["ORACLE_DSN"])


def half_even(value: Decimal) -> Decimal:
    """.NET Math.Round(decimal, 2): what the hub's C# functoids (ComputeReserve, FormatMoney) do."""
    return value.quantize(CENT, rounding=ROUND_HALF_EVEN)


def half_up(value: Decimal) -> Decimal:
    """XSLT round() over absolute cents: what Payment_to_VendorRemittance does per line. Also Oracle ROUND."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def read_xml(path: Path) -> ET.Element:
    return ET.parse(path).getroot()


def text(node: ET.Element, path: str, default: str | None = None) -> str | None:
    found = node.find(path)
    if found is None or found.text is None:
        return default
    return found.text.strip()


def money(node: ET.Element, path: str) -> Decimal:
    return Decimal(text(node, path))
