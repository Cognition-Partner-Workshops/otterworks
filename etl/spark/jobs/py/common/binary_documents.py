import hashlib
from io import BytesIO
import re
import pyexpat
from zipfile import BadZipFile, ZipFile


def document_text(content):
    parser = pyexpat.ParserCreate(namespace_separator="}")
    paragraphs = []
    depth = 0

    def start(name, attributes):
        nonlocal depth
        if depth:
            depth += 1
        elif name == "http://schemas.openxmlformats.org/wordprocessingml/2006/main}t":
            depth = 1
            paragraphs.append([])

    def end(name):
        nonlocal depth
        if depth:
            depth -= 1

    def text(value):
        if depth:
            paragraphs[-1].append(value)

    def reject(*arguments):
        raise ValueError("Document type declarations and external entities are not supported")

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CharacterDataHandler = text
    parser.StartDoctypeDeclHandler = reject
    parser.ExternalEntityRefHandler = reject
    parser.Parse(content, True)
    return "\n".join("".join(parts) for parts in paragraphs)


def extract_document(content):
    raw = bytes(content)
    digest = hashlib.sha256(raw).hexdigest()
    try:
        if raw.startswith(b"%PDF-"):
            text = "\n".join(part.decode("utf-8", "replace") for part in re.findall(rb"\((.*?)\) Tj", raw))
            pages = len(re.findall(rb"/Type /Page\b", raw))
            if not pages:
                raise ValueError("PDF contains no page objects")
            return "application/pdf", text[:4096], pages, digest, None
        with ZipFile(BytesIO(raw)) as archive:
            if "word/document.xml" in archive.namelist():
                text = document_text(archive.read("word/document.xml"))
                return "application/vnd.openxmlformats-officedocument.wordprocessingml.document", text[:4096], max(1, (len(text) + 2999) // 3000), digest, None
            text = "\n".join(archive.read(name).decode("utf-8", "replace") for name in archive.namelist() if name.endswith(".txt"))
            return "application/zip", text[:4096], max(1, text.count("\f") + 1), digest, None
    except (BadZipFile, pyexpat.ExpatError, ValueError, OSError) as error:
        return "application/octet-stream", "", 0, digest, str(error)[:200]
