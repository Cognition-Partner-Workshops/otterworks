import os

ESTATE_BACKENDS = ("oracle", "ow_billing_pg")


class UsageRejected(Exception):
    """The estate refused a usage event (TRG_USAGE_EVENTS_CHK business rule)."""


def get_backend():
    name = os.getenv("BILLING_BACKEND", "postgres").lower()
    if name == "oracle":
        from . import oracle

        return oracle
    if name == "ow_billing_pg":
        from . import ow_billing_pg

        return ow_billing_pg
    from . import postgres

    return postgres


def backend_name():
    return get_backend().NAME
