"""MongoDB backend for the migrated invoice estate (ow_billing_migration).

Only the surfaces owned by unit u-06 are implemented: the month-end RPT-114
rollup read paths over ``invoiceHeader`` (with embedded ``lines[]``). Every
other facade surface raises ``NotImplementedError`` via ``__getattr__``.

pymongo is imported lazily inside functions so this module — and anything
importing the backends package — works without pymongo installed.
"""

import os
from decimal import Decimal

NAME = "mongo"

LINE_TYPES = {1: "CHARGE", 2: "CREDIT", 3: "ADJUSTMENT", 9: "MISC"}


def get_client():
    from pymongo import MongoClient

    return MongoClient(os.getenv("MONGO_LOCAL_URI", "mongodb://localhost:27017"))


def get_db(client=None):
    client = client if client is not None else get_client()
    return client[os.getenv("MONGO_DB", "ow_billing_migration")]


def health():
    get_db().command("ping")


def _codes_lookup():
    return {
        "$lookup": {
            "from": "codes",
            "let": {"cd": "$statusCd"},
            "pipeline": [
                {
                    "$match": {
                        "$expr": {
                            "$and": [
                                {"$eq": ["$codeType", "INV_STATUS"]},
                                {"$eq": ["$codeVal", "$$cd"]},
                            ]
                        }
                    }
                }
            ],
            "as": "st",
        }
    }


def _status_label(status_cd, code_desc):
    if code_desc:
        return code_desc
    return f"UNKNOWN({'' if status_cd is None else status_cd})"


def _line_type_label(line_type_cd):
    if line_type_cd is None:
        return "UNKNOWN()"
    return LINE_TYPES.get(int(line_type_cd), f"UNKNOWN({line_type_cd})")


def _money(value):
    if value is None:
        return None
    if hasattr(value, "to_decimal"):
        value = value.to_decimal()
    amount = Decimal(value).quantize(Decimal("0.01"))
    return format(amount, "f")


def month_end_status_rows(db, batch_no):
    """RPT-114 by_status rollup over invoiceHeader for one batch.

    Returns tuples ``(status_desc, invoice_count, header_total_amt)`` in the
    same shape and order as the Oracle STATUS_SQL rows: sorted by status_desc
    with binary (plain string) collation.
    """
    pipeline = [
        {"$match": {"batchNo": batch_no}},
        _codes_lookup(),
        {
            "$project": {
                "statusCd": 1,
                "totalAmt": 1,
                "codeDesc": {"$first": "$st.codeDesc"},
            }
        },
        {
            "$group": {
                "_id": {"cd": "$statusCd", "desc": "$codeDesc"},
                "invoice_count": {"$sum": 1},
                "header_total_amt": {"$sum": "$totalAmt"},
            }
        },
    ]
    rows = [
        (
            _status_label(doc["_id"]["cd"], doc["_id"]["desc"]),
            int(doc["invoice_count"]),
            _money(doc["header_total_amt"]),
        )
        for doc in db["invoiceHeader"].aggregate(pipeline)
    ]
    return sorted(rows, key=lambda row: row[0])


def month_end_line_rows(db, batch_no):
    """RPT-114 by_status_line_type rollup over invoiceHeader.lines.

    Returns tuples ``(status_desc, line_type, line_count, line_amount,
    line_tax, invoices_touched)`` ordered by (status_desc, line_type).
    Orphan lines are absent from ``lines`` — the legacy inner join for free.
    """
    pipeline = [
        {"$match": {"batchNo": batch_no}},
        {"$unwind": "$lines"},
        _codes_lookup(),
        {
            "$project": {
                "statusCd": 1,
                "lineTypeCd": "$lines.lineTypeCd",
                "amount": "$lines.amount",
                "taxAmt": "$lines.taxAmt",
                "codeDesc": {"$first": "$st.codeDesc"},
            }
        },
        {
            "$group": {
                "_id": {
                    "cd": "$statusCd",
                    "desc": "$codeDesc",
                    "lt": "$lineTypeCd",
                },
                "line_count": {"$sum": 1},
                "line_amount": {"$sum": "$amount"},
                "line_tax": {"$sum": "$taxAmt"},
                "invoices": {"$addToSet": "$_id"},
            }
        },
        {
            "$project": {
                "line_count": 1,
                "line_amount": 1,
                "line_tax": 1,
                "invoices_touched": {"$size": "$invoices"},
            }
        },
    ]
    rows = [
        (
            _status_label(doc["_id"]["cd"], doc["_id"]["desc"]),
            _line_type_label(doc["_id"]["lt"]),
            int(doc["line_count"]),
            _money(doc["line_amount"]),
            _money(doc["line_tax"]),
            int(doc["invoices_touched"]),
        )
        for doc in db["invoiceHeader"].aggregate(pipeline)
    ]
    return sorted(rows, key=lambda row: (row[0], row[1]))


def __getattr__(name):
    if name.startswith("__"):
        raise AttributeError(name)
    raise NotImplementedError(
        f"backends.mongo.{name}: only the month-end report and CUSTBILL "
        "surfaces are implemented on the MongoDB backend (unit u-06)"
    )
