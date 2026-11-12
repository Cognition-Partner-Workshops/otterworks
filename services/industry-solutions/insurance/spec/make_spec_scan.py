#!/usr/bin/env python3
"""Render the product and commission specification as an image-only scanned PDF.

Usage: python3 make_spec_scan.py [output.pdf]   (requires Pillow)
"""
from __future__ import annotations

import random
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

DPI = 200
PAGE = (1700, 2200)
MARGIN = 170
SEED = 1114

FONT_DIRS = (
    "/usr/share/fonts/truetype/liberation",
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/liberation",
    "/Library/Fonts",
)
FONT_FILES = {
    "body": ("LiberationSerif-Regular.ttf", "DejaVuSerif.ttf"),
    "bold": ("LiberationSerif-Bold.ttf", "DejaVuSerif-Bold.ttf"),
    "mono": ("LiberationMono-Regular.ttf", "DejaVuSansMono.ttf"),
}

HEADER = "OTTERWORKS LIFE AND ANNUITY COMPANY"
FORM = "Form CP-114  Rev. 3"

PAGES = [
    [
        ("title", "PRODUCT AND COMMISSION SPECIFICATION"),
        ("center", "Individual Life and Annuity -- Agency Distribution"),
        ("center", "Compensation Plan CP-114, Revision 3"),
        ("gap", ""),
        ("mono", "Effective: July 1, 2025          Supersedes: CP-114 Rev. 2 (2019)"),
        ("mono", "Owner: Agency Compensation      Distribution: Commission Operations"),
        ("rule", ""),
        ("head", "1.  SCOPE"),
        ("para", "This specification sets out the products available for sale through the "
                 "career agency channel and the commission payable to writing agents on "
                 "those products."),
        ("head", "2.  PRODUCTS"),
        ("table", [("Code", "Product", "Line", "Basis"),
                   ("TERM-20", "20-Year Term Life", "Life", "Flat rate"),
                   ("WL-PAR", "Participating Whole Life", "Life", "Tiered"),
                   ("FIA-7", "7-Year Fixed Indexed Annuity", "Annuity", "Tiered")]),
        ("para", "Premium for commission purposes is the annualized planned premium shown "
                 "on the policy schedule. For FIA-7 the single premium is treated as the "
                 "annualized premium."),
        ("head", "3.  PREMIUM TIERS"),
        ("para", "Tiered products pay a first-year rate that depends on the premium tier "
                 "of the policy at issue:"),
        ("bullet", "Tier 1 (T1): annualized premium under $50,000."),
        ("bullet", "Tier 2 (T2): annualized premium of $50,000 or more."),
        ("para", "The tier is fixed at issue and does not change if premium is later "
                 "adjusted."),
    ],
    [
        ("head", "4.  COMMISSION RATES"),
        ("table", [("Product", "Tier", "Rate", "In effect"),
                   ("TERM-20", "--", "15.00%", "Jan 1, 2024"),
                   ("WL-PAR", "T1", "45.00%", "Jan 1, 2020 - Jun 30, 2025"),
                   ("WL-PAR", "T1", "40.00%", "Jul 1, 2025"),
                   ("WL-PAR", "T2", "30.00%", "Jan 1, 2020"),
                   ("FIA-7", "T1", "6.00%", "Jan 1, 2020"),
                   ("FIA-7", "T2", "4.50%", "Jan 1, 2020")]),
        ("para", "4.1  For tiered products the rate is the rate in effect on the policy "
                 "issue date. A policy issued on the date a new rate takes effect is paid "
                 "at the new rate."),
        ("para", "4.2  Commission is paid monthly. The monthly commission for an agent on "
                 "a policy is one twelfth of the annualized premium, multiplied by the "
                 "rate, multiplied by the agent's split percentage, rounded to the cent."),
        ("para", "4.3  Where two or more agents share a policy, split percentages must be "
                 "recorded for every agent and must total exactly 100%."),
        ("head", "5.  MONTHLY LIMIT"),
        ("para", "Total commission payable to any one agent for a calendar month, across "
                 "all policies, is limited to $2,500.00. Amounts above the limit are not "
                 "carried forward."),
    ],
    [
        ("head", "6.  CHARGEBACKS"),
        ("para", "6.1  When a policy lapses or is surrendered during the first policy "
                 "year, commission already paid to the writing agents on that policy is "
                 "charged back according to the number of months the policy was in force:"),
        ("table", [("Months in force", "Chargeback"),
                   ("1 through 6", "100% of commission paid"),
                   ("7 through 12", "50% of commission paid"),
                   ("13 and later", "None")]),
        ("para", "6.2  The chargeback is booked in the month the lapse is processed and "
                 "is shared among the agents in the same proportion as the commission "
                 "was paid."),
        ("head", "7.  APPROVAL"),
        ("gap", ""),
        ("mono", "Agency Compensation  ______________________   Date ___________"),
        ("gap", ""),
        ("mono", "Product Actuarial    ______________________   Date ___________"),
        ("gap", ""),
        ("mono", "Commission Ops       ______________________   Date ___________"),
    ],
]


def load_font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    for name in FONT_FILES[kind]:
        for d in FONT_DIRS:
            path = Path(d) / name
            if path.exists():
                return ImageFont.truetype(str(path), size)
    raise SystemExit(f"no font found for {kind}: install fonts-liberation or fonts-dejavu")


def wrap(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= width:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def render_page(blocks, page_no: int, total: int) -> Image.Image:
    img = Image.new("L", PAGE, 255)
    d = ImageDraw.Draw(img)
    body, bold, mono = load_font("body", 34), load_font("bold", 36), load_font("mono", 28)
    small = load_font("body", 26)
    width = PAGE[0] - 2 * MARGIN

    d.text((MARGIN, 110), HEADER, font=small, fill=40)
    d.text((PAGE[0] - MARGIN - d.textlength(FORM, font=small), 110), FORM, font=small, fill=40)
    d.line((MARGIN, 150, PAGE[0] - MARGIN, 150), fill=60, width=2)
    y = 200

    for kind, content in blocks:
        if kind == "title":
            f = load_font("bold", 48)
            d.text(((PAGE[0] - d.textlength(content, font=f)) / 2, y), content, font=f, fill=10)
            y += 80
        elif kind == "center":
            d.text(((PAGE[0] - d.textlength(content, font=body)) / 2, y), content, font=body, fill=20)
            y += 50
        elif kind == "gap":
            y += 30
        elif kind == "rule":
            d.line((MARGIN, y + 10, PAGE[0] - MARGIN, y + 10), fill=60, width=2)
            y += 40
        elif kind == "mono":
            d.text((MARGIN, y), content, font=mono, fill=20)
            y += 44
        elif kind == "head":
            y += 20
            d.text((MARGIN, y), content, font=bold, fill=10)
            y += 62
        elif kind == "para":
            for line in wrap(d, content, body, width):
                d.text((MARGIN, y), line, font=body, fill=20)
                y += 46
            y += 18
        elif kind == "bullet":
            d.text((MARGIN + 30, y), "\u2022", font=body, fill=20)
            for line in wrap(d, content, body, width - 70):
                d.text((MARGIN + 70, y), line, font=body, fill=20)
                y += 46
            y += 6
        elif kind == "table":
            cols = len(content[0])
            col_w = [max(d.textlength(r[i], font=body) for r in content) + 50 for i in range(cols)]
            x0 = MARGIN + 20
            top = y
            for r, row in enumerate(content):
                x = x0
                for i, cell in enumerate(row):
                    d.text((x + 14, y + 8), cell, font=bold if r == 0 else body, fill=15)
                    x += col_w[i]
                y += 54
                d.line((x0, y, x, y), fill=70, width=2 if r == 0 else 1)
            d.rectangle((x0, top, x0 + sum(col_w), y), outline=50, width=2)
            x = x0
            for w in col_w[:-1]:
                x += w
                d.line((x, top, x, y), fill=70, width=1)
            y += 36

    footer = f"Page {page_no} of {total}"
    d.text(((PAGE[0] - d.textlength(footer, font=small)) / 2, PAGE[1] - 130), footer, font=small, fill=40)
    return img


def degrade(img: Image.Image, rng: random.Random) -> Image.Image:
    w, h = img.size
    img = img.filter(ImageFilter.GaussianBlur(0.8))
    noise = Image.frombytes("L", (w, h), rng.randbytes(w * h)).filter(ImageFilter.GaussianBlur(0.6))
    img = Image.blend(img, noise, 0.10)
    d = ImageDraw.Draw(img)
    for _ in range(900):
        x, y, r = rng.randrange(w), rng.randrange(h), rng.choice((1, 1, 1, 2, 2, 3))
        d.ellipse((x, y, x + r, y + r), fill=rng.randrange(40, 140))
    x = rng.randrange(60, 110)
    d.line((x, 0, x + rng.randrange(-6, 6), h), fill=205, width=3)
    img = img.point(lambda v: 0 if v < 70 else (255 if v > 215 else v))
    angle = rng.uniform(0.45, 0.9) * rng.choice((-1, 1))
    img = img.rotate(angle, resample=Image.BICUBIC, expand=False, fillcolor=238)
    shade = Image.linear_gradient("L").resize((w, h)).point(lambda v: 232 + v * 18 // 255)
    return Image.composite(img, shade, img.point(lambda v: 255 if v < 230 else 0))


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("cp114-commission-spec-scan.pdf")
    rng = random.Random(SEED)
    pages = [degrade(render_page(b, i + 1, len(PAGES)), rng) for i, b in enumerate(PAGES)]
    stamp = time.gmtime(1752070920)
    pages[0].save(out, "PDF", save_all=True, append_images=pages[1:], resolution=DPI, quality=55,
                  title="CP-114 Rev 3 scan", producer="Scan", creator="Scan",
                  creationDate=stamp, modDate=stamp)
    print(out)


if __name__ == "__main__":
    main()
