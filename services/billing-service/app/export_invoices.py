from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import asdict, fields
from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile

from app.warehouse.teradata import (
    InvoiceExportRow,
    InvoiceWarehouse,
    TeradataInvoiceWarehouse,
    WarehouseSettings,
)


def export_invoices(
    warehouse: InvoiceWarehouse,
    run_date: date | None,
    out: Path,
    *,
    enabled: bool = True,
) -> int:
    if not enabled:
        raise RuntimeError("finance warehouse export is disabled")
    rows = warehouse.invoices_for_run(run_date)
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=out.parent,
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            writer = csv.DictWriter(
                stream, fieldnames=[field.name for field in fields(InvoiceExportRow)]
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(asdict(row))
        temporary.replace(out)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export the prior day's finance warehouse invoices"
    )
    parser.add_argument(
        "--date", type=date.fromisoformat, help="run date YYYY-MM-DD (default: TD today)"
    )
    parser.add_argument("--out", type=Path, required=True, help="CSV output path")
    args = parser.parse_args(argv)
    try:
        settings = WarehouseSettings()
        count = export_invoices(
            TeradataInvoiceWarehouse(settings),
            args.date,
            args.out,
            enabled=settings.enabled,
        )
    except Exception:
        print("invoice export failed; check warehouse settings and output path", file=sys.stderr)
        return 1
    print(f"Exported {count} invoices to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
