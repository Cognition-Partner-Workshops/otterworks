"""Native receivables query; retain the emulator's numeric division contract."""
import os
from datetime import date
from decimal import Decimal, ROUND_HALF_UP, localcontext
from pathlib import Path

from databricks_warehouse import execute
from finance_warehouse import TeradataReceivablesWarehouse

SQL = Path(__file__).with_name("ar_aging_databricks.sql").read_text()


def source_ratio(numerator, denominator):
    """PostgreSQL numeric division uses base-10000 weights and 16 significant digits.

    The bridge is the source oracle. Spark's decimal division reduces scale to
    six for these sums, so compute only this scalar after warehouse aggregation.
    """
    if denominator is None or denominator == 0 or numerator is None:
        return None
    a, b = Decimal(numerator), Decimal(denominator)
    with localcontext() as context:
        context.prec = 100
        wa = a.copy_abs().adjusted() // 4 if a else 0
        wb = b.copy_abs().adjusted() // 4
        first_a = int(abs(a).scaleb(-4 * wa))
        first_b = int(abs(b).scaleb(-4 * wb))
        weight = wa - wb - (first_a <= first_b)
        scale = max(16 - weight * 4, -a.as_tuple().exponent, -b.as_tuple().exponent, 0)
        return (a / b).quantize(Decimal(1).scaleb(-scale), rounding=ROUND_HALF_UP)


class DatabricksReceivablesWarehouse:
    def __init__(self, as_of=None):
        pinned = as_of or os.getenv("FINANCE_WAREHOUSE_AS_OF")
        self.as_of = date.fromisoformat(pinned) if pinned else None
        self.last_result = None

    def ar_aging(self):
        as_of = self.as_of or date.today()
        result = execute(SQL, [as_of.isoformat()] * 5, step="contract-fixed")
        self.last_result = result
        rows = []
        for values in result["rows"]:
            values = list(values)
            values[-1] = source_ratio(values[4], values[-1])
            rows.append(TeradataReceivablesWarehouse._map_row(values))
        return rows
