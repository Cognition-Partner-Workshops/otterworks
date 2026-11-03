#!/usr/bin/env python3
"""Download each photo in images.csv once, resize, convert to WebP and write IMAGE_CREDITS.md.

Usage: python3 tools/catalog/fetch_images.py [--force]
Writes frontend/client-app/public/images/{products,editorial}/<name>.webp (1200 px long edge)
and <name>-sm.webp (600 px). Existing files are skipped unless --force is given.
"""
import csv
import io
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
CSV = ROOT / "tools/catalog/images.csv"
OUT = ROOT / "frontend/client-app/public/images"
CREDITS = ROOT / "frontend/client-app/IMAGE_CREDITS.md"
FORCE = "--force" in sys.argv


def fetch(row):
    dest = OUT / row["file"]
    small = dest.with_name(dest.stem + "-sm.webp")
    if dest.exists() and small.exists() and not FORCE:
        return row["file"], "skip"
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(row["download_url"], headers={"User-Agent": "ottershops-catalog/1.0"})
    data = urllib.request.urlopen(req, timeout=60).read()
    im = Image.open(io.BytesIO(data)).convert("RGB")
    for path, edge in ((dest, 1200), (small, 600)):
        copy = im.copy()
        copy.thumbnail((edge, edge), Image.LANCZOS)
        copy.save(path, "WEBP", quality=80, method=6)
    return row["file"], "ok"


def write_credits(rows):
    lines = [
        "# Image credits",
        "",
        "All photos come from [Unsplash](https://unsplash.com) and are used under the",
        "[Unsplash License](https://unsplash.com/license): free for commercial and non-commercial use,",
        "no permission or attribution required (we credit each photographer anyway). Photos may not be",
        "sold unaltered or used to build a competing photo service.",
        "",
        "Photos were picked by hand and checked for visible logos, store signs and famous people.",
        "Product names, brands and prices on this site are invented; the photos do not show OtterShops products.",
        "",
        "| File | Photographer | Source | License |",
        "|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| `public/images/{r['file']}` | [{r['photographer']}]({r['photographer_url']}) "
            f"| [Unsplash]({r['source_url']}) | {r['license']} |"
        )
    CREDITS.write_text("\n".join(lines) + "\n")


def main():
    rows = list(csv.DictReader(CSV.open()))
    with ThreadPoolExecutor(8) as ex:
        for name, status in ex.map(fetch, rows):
            if status != "skip":
                print(status, name)
    write_credits(rows)
    total = sum(p.stat().st_size for p in OUT.rglob("*.webp"))
    print(f"{len(rows)} photos, {total / 1e6:.1f} MB in {OUT}")


if __name__ == "__main__":
    main()
