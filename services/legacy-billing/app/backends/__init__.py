import os


def get_backend():
    name = os.getenv("BILLING_BACKEND", "postgres").lower()
    if name == "oracle":
        from . import oracle

        return oracle
    if name == "mongo":
        from . import mongo

        return mongo
    from . import postgres

    return postgres


def backend_name():
    module = get_backend()
    if module.__name__.endswith(".oracle"):
        return "oracle"
    if module.__name__.endswith(".mongo"):
        return "mongo"
    return "postgres"
