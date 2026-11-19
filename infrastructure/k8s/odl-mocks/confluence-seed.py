import json
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def request(path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = Request("http://127.0.0.1:8080/wiki/api/v2" + path, data=data,
                  headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=10) as response:
        return json.load(response)


def reconcile(pages):
    if not pages:
        return
    spaces = request("/spaces?keys=ENG")["results"]
    if len(spaces) != 1:
        raise ValueError("Expected ENG space")
    space_id = spaces[0]["id"]
    for page in pages:
        query = urlencode({"space-id": space_id, "title": page["title"]})
        if not request("/pages?" + query)["results"]:
            result = request("/pages", {"spaceId": space_id, **page})
            print("seeded", result["id"], page["title"], flush=True)


def main():
    pages = json.loads(Path("/seed/confluence-seed.json").read_text())
    while True:
        try:
            reconcile(pages)
        except (HTTPError, URLError, TimeoutError, ConnectionError, ValueError, KeyError) as error:
            print("seed retry:", type(error).__name__, flush=True)
        time.sleep(10)


if __name__ == "__main__":
    main()
