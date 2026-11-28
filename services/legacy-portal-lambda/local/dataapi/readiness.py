from ssl import create_default_context
from urllib.request import HTTPSHandler, ProxyHandler, build_opener


def check(ca_file="/certs/ca.pem"):
    tls = create_default_context(cafile=ca_file)
    opener = build_opener(ProxyHandler({}), HTTPSHandler(context=tls))
    for url in ("http://127.0.0.1:8080/ping", "https://dataapi/ping"):
        with opener.open(url, timeout=2) as response:
            if response.status != 200:
                raise RuntimeError(f"{url} returned HTTP {response.status}")


if __name__ == "__main__":
    check()
