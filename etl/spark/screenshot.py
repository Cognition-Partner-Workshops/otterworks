#!/usr/bin/env python3
"""Save full-page Jobs and heaviest-stage History Server screenshots."""
import argparse
import json
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen


def heaviest_stage(stages):
    if not stages:
        raise ValueError("Application has no stages")
    return max(stages, key=lambda stage: (stage.get("executorRunTime", 0), stage["stageId"], stage["attemptId"]))


def capture(app, output, history="http://localhost:18080", executable=None):
    from playwright.sync_api import sync_playwright

    base = history.rstrip("/")
    identity = quote(app, safe="")
    with urlopen(f"{base}/api/v1/applications/{identity}/stages", timeout=60) as response:
        stage = heaviest_stage(json.load(response))
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    pages = {
        "jobs": f"{base}/history/{identity}/jobs/",
        "stage": f"{base}/history/{identity}/stages/stage/?id={stage['stageId']}&attempt={stage['attemptId']}",
    }
    paths = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=executable)
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
            for kind, url in pages.items():
                response = page.goto(url, wait_until="networkidle")
                if response is None or not response.ok:
                    raise RuntimeError(f"History page failed: {url}")
                page.wait_for_selector("h4")
                path = output / f"{app}-{kind}.png"
                page.screenshot(path=str(path), full_page=True)
                paths.append(str(path))
        finally:
            browser.close()
    return paths


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--history", default="http://localhost:18080")
    parser.add_argument("--executable", help="Optional installed Chromium executable")
    args = parser.parse_args()
    print("\n".join(capture(args.app, args.output, args.history, args.executable)))
