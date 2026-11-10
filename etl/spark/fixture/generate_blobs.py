#!/usr/bin/env python3
"""Build a small binary document store."""
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_STORED


def pdf(text):
    lines = text.splitlines()
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b""]
    pages = []
    for start in range(0, len(lines), 70):
        page_id = len(objects) + 1
        stream_id = page_id + 1
        font_id = page_id + 2
        pages.append(page_id)
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {stream_id} 0 R >>".encode())
        commands = ["BT /F1 9 Tf 40 750 Td 10 TL"]
        for line in lines[start:start + 70]:
            escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            commands.append(f"({escaped}) Tj T*")
        stream = ("\n".join(commands) + "\nET").encode()
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream")
        objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objects[1] = f"<< /Type /Pages /Count {len(pages)} /Kids [{' '.join(f'{p} 0 R' for p in pages)}] >>".encode()
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{i} 0 obj\n".encode() + obj + b"\nendobj\n")
    location = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        output.extend(f"{offset:010} 00000 n \n".encode())
    output.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{location}\n%%EOF\n".encode())
    return bytes(output)


def zipped(text, docx):
    output = BytesIO()
    with ZipFile(output, "w", ZIP_STORED) as archive:
        def add(name, data):
            entry = ZipInfo(name, (2026, 11, 9, 0, 0, 0))
            archive.writestr(entry, data)
        if docx:
            add("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
            add("_rels/.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
            paragraphs = "".join(f"<w:p><w:r><w:t>{line}</w:t></w:r></w:p>" for line in text.splitlines())
            add("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>' + paragraphs + "</w:body></w:document>")
        else:
            add("operating-review.txt", text)
            add("manifest.txt", "Document export\nPrepared: 2026-11-09\nClassification: Internal\n")
    return output.getvalue()


def generate_blobs(landing, rows, seed):
    folder = landing / "documents" / "FILE_OBJECT_BLOBS"
    folder.mkdir(parents=True, exist_ok=True)
    count = min(768, max(1, rows // 250)) if rows else 0
    metadata = []
    for i in range(count):
        extension = ("pdf", "docx", "zip")[i % 3]
        name = f"review-{sha256(f'{seed}:{i}'.encode()).hexdigest()[:20]}.{extension}"
        lines = [f"Operating review section {section + 1}: approve the service schedule and reconcile revenue for reporting period November 2026. Reference {i + 41000}."
                 for section in range(1800)]
        text = "\n".join(lines)
        content = pdf(text) if extension == "pdf" else zipped(text, extension == "docx")
        path = folder / name
        path.write_bytes(content)
        metadata.append({
            "STORAGE_KEY": f"documents/FILE_OBJECT_BLOBS/{name}",
            "SIZE_BYTES": len(content), "CHECKSUM": sha256(content).hexdigest(),
        })
    expected = {Path(row["STORAGE_KEY"]).name for row in metadata}
    for path in folder.iterdir():
        if path.is_file() and path.name not in expected:
            path.unlink()
    return metadata
