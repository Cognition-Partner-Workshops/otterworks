import json
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def request(path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = Request("http://127.0.0.1:8080" + path, data=data,
                  headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=10) as response:
        return json.load(response)


def reconcile(issues):
    for issue in issues:
        label = issue["seed_label"]
        query = urlencode({"jql": f'project = ENG AND labels = "{label}"'})
        found = request("/rest/api/3/search?" + query)["issues"]
        if not found:
            result = request("/rest/api/3/issue", {"fields": issue["fields"]})
            print("seeded", result["key"], label, flush=True)


def main():
    issues = json.loads(Path("/seed/seed.json").read_text())
    while True:
        try:
            reconcile(issues)
        except (HTTPError, URLError, TimeoutError, ConnectionError, ValueError, KeyError) as error:
            print("seed retry:", type(error).__name__, flush=True)
        time.sleep(10)


if __name__ == "__main__":
    main()
