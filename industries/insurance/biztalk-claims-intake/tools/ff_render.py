#!/usr/bin/env python3
"""Render Remittance map output (XML) to the positional text the BizTalk flat file assembler would write.

Field widths, justification and pad characters are read from Schemas/PaymentVendor_Remittance_FF.xsd
so the schema stays the single source of truth. Records end with CRLF; the file is US-ASCII.
Writes corpus/golden/vendor-remittance-ff/<name>.txt for every file under corpus/golden/vendor-remittance.
"""
from __future__ import annotations

import os
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
XS = "{http://www.w3.org/2001/XMLSchema}"
B = "{http://schemas.microsoft.com/BizTalk/2003}"


def load_layout(xsd_path: str) -> dict[str, list[tuple[str, int, str, str]]]:
    tree = ET.parse(xsd_path)
    layout: dict[str, list[tuple[str, int, str, str]]] = {}
    root = tree.getroot().find(f"{XS}element")
    for record in root.iter(f"{XS}element"):
        info = record.find(f".//{B}recordInfo")
        if info is None or info.get("structure") != "positional":
            continue
        fields = []
        for field in record.find(f"{XS}complexType").iter(f"{XS}element"):
            finfo = field.find(f".//{B}fieldInfo")
            fields.append((field.get("name"), int(finfo.get("pos_length")), finfo.get("justification", "left"), finfo.get("pad_char", " ")))
        layout[record.get("name")] = fields
    return layout


def render_record(element: ET.Element, fields) -> str:
    out = []
    for name, length, justification, pad in fields:
        value = (element.findtext(name) or "")[:length]
        out.append(value.rjust(length, pad) if justification == "right" else value.ljust(length, pad))
    return "".join(out)


def render(xml_path: str, layout) -> str:
    root = ET.parse(xml_path).getroot()
    lines = []
    for child in root:
        lines.append(render_record(child, layout[child.tag]))
    return "\r\n".join(lines) + "\r\n"


def main() -> int:
    layout = load_layout(os.path.join(ROOT, "Schemas", "PaymentVendor_Remittance_FF.xsd"))
    src = os.path.join(ROOT, "corpus", "golden", "vendor-remittance")
    dst = os.path.join(ROOT, "corpus", "golden", "vendor-remittance-ff")
    check = len(sys.argv) > 1 and sys.argv[1] == "check"
    os.makedirs(dst, exist_ok=True)
    failures = 0
    for name in sorted(os.listdir(src)):
        text = render(os.path.join(src, name), layout)
        target = os.path.join(dst, name.replace(".xml", ".txt"))
        if check:
            with open(target, "rb") as fh:
                if fh.read() != text.encode("ascii"):
                    failures += 1
                    print(f"  DIFF    {name}")
        else:
            with open(target, "wb") as fh:
                fh.write(text.encode("ascii"))
    print(f"vendor-remittance-ff: {len(os.listdir(src))} files, failures {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
