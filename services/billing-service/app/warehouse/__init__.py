from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Protocol

MAX_INVOICES = 100000


@dataclass(frozen=True)
class InvoiceExportRow:
    invoice_no: str
    customer_name: str
    account_no: str
    invoice_date: date
    currency_cd: str
    amount_due: Decimal
    tax_amt: Decimal
    open_balance: Decimal

    @classmethod
    def from_values(cls, values: list[Any] | tuple[Any, ...]) -> InvoiceExportRow:
        invoice_no, customer, account, issued, currency, amount, tax, balance = values
        return cls(
            str(invoice_no),
            str(customer),
            str(account).strip(),
            issued if isinstance(issued, date) else date.fromisoformat(str(issued).strip()),
            str(currency).strip(),
            Decimal(str(amount).strip()),
            Decimal(str(tax).strip()),
            Decimal(str(balance).strip()),
        )


class InvoiceWarehouse(Protocol):
    def invoices_for_run(self, run_date: date | None) -> list[InvoiceExportRow]: ...
