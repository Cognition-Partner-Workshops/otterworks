import datetime as dt
import os
import threading
from http.server import ThreadingHTTPServer

import dataapi

original_field = dataapi.field


def drift_field(value):
    if isinstance(value, dt.datetime):
        timestamp = value.replace(tzinfo=dt.UTC) if value.tzinfo is None else value
        return {"stringValue": timestamp.isoformat()}
    return original_field(value)


def main():
    dataapi.field = drift_field
    if cert := os.getenv("TLS_CERT"):
        tls = (int(os.getenv("TLS_PORT", "443")), cert, os.environ["TLS_KEY"])
        threading.Thread(target=dataapi.serve_tls, args=tls, daemon=True).start()
    address = ("0.0.0.0", int(os.getenv("PORT", "8080")))
    with ThreadingHTTPServer(address, dataapi.Handler) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
