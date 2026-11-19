"""Documents binary media, bounded text, page estimates and observable errors."""

import hashlib
import re
from io import BytesIO
from xml.parsers import expat
from zipfile import BadZipFile, ZipFile


def document_text(content):
    parser = expat.ParserCreate(namespace_separator='}')
    parts, depth = [], 0

    def start(name, attributes):
        nonlocal depth
        if depth:
            depth += 1
        elif name == 'http://schemas.openxmlformats.org/wordprocessingml/2006/main}t':
            depth = 1
            parts.append([])

    def end(name):
        nonlocal depth
        if depth:
            depth -= 1

    def text(value):
        if depth:
            parts[-1].append(value)

    def reject(*arguments):
        raise ValueError('Document type declarations and external entities are not supported')

    parser.StartElementHandler, parser.EndElementHandler = start, end
    parser.CharacterDataHandler = text
    parser.StartDoctypeDeclHandler = parser.ExternalEntityRefHandler = reject
    parser.Parse(content, True)
    return '\n'.join(''.join(part) for part in parts)


def extract_document(content):
    raw = bytes(content)
    digest = hashlib.sha256(raw).hexdigest()
    try:
        if raw.startswith(b'%PDF-'):
            text = '\n'.join(value.decode('utf-8', 'replace') for value in re.findall(rb'\((.*?)\) Tj', raw))
            pages = len(re.findall(rb'/Type /Page\b', raw))
            if not pages:
                raise ValueError('PDF contains no page objects')
            return 'application/pdf', text[:4096], pages, digest, None
        with ZipFile(BytesIO(raw)) as archive:
            if 'word/document.xml' in archive.namelist():
                text = document_text(archive.read('word/document.xml'))
                media = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                return media, text[:4096], max(1, (len(text) + 2999) // 3000), digest, None
            text = '\n'.join(archive.read(name).decode('utf-8', 'replace') for name in archive.namelist() if name.endswith('.txt'))
            return 'application/zip', text[:4096], max(1, text.count('\f') + 1), digest, None
    except (BadZipFile, expat.ExpatError, ValueError, OSError) as error:
        return 'application/octet-stream', '', 0, digest, str(error)[:200]
