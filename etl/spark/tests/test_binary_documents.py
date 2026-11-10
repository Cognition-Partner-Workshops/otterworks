import hashlib
from io import BytesIO
from pathlib import Path
import sys
import tempfile
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "fixture"))
sys.path.insert(0, str(ROOT / "jobs/py"))
from generate_blobs import generate_blobs, pdf, zipped
from common.binary_documents import extract_document


class BinaryDocumentTest(unittest.TestCase):
    def test_supported_documents(self):
        text = "Monthly revenue review\nApprove the operating forecast."
        for content, media in ((pdf(text), "application/pdf"),
                               (zipped(text, True), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
                               (zipped(text, False), "application/zip")):
            result = extract_document(content)
            self.assertEqual(result[0], media)
            self.assertIn("Monthly revenue review", result[1])
            self.assertGreater(result[2], 0)
            self.assertEqual(result[3], hashlib.sha256(content).hexdigest())
            self.assertIsNone(result[4])

    def test_empty_and_invalid(self):
        for content in (b"", b"not a document", b"%PDF-1.4\ninvalid"):
            result = extract_document(content)
            self.assertEqual(result[0], "application/octet-stream")
            self.assertEqual(result[2], 0)
            self.assertIsNotNone(result[4])

    def test_document_xml(self):
        for xml, expected in (
            (b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:t>Revenue &amp; costs</w:t></w:document>', "Revenue & costs"),
            (b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>', ""),
            (b"<!DOCTYPE document><document/>", None),
            (b"<document>", None),
        ):
            content = BytesIO()
            with ZipFile(content, "w") as archive:
                archive.writestr("word/document.xml", xml)
            result = extract_document(content.getvalue())
            if expected is None:
                self.assertEqual(result[0], "application/octet-stream")
                self.assertIsNotNone(result[4])
            else:
                self.assertEqual(result[1], expected)
                self.assertIsNone(result[4])

    def test_blob_store_repeatability_and_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = generate_blobs(root, 750, 1110)
            self.assertEqual(len(first), 3)
            self.assertEqual(first, generate_blobs(root, 750, 1110))
            for row in first:
                content = (root / row["STORAGE_KEY"]).read_bytes()
                self.assertEqual(len(content), row["SIZE_BYTES"])
                self.assertEqual(hashlib.sha256(content).hexdigest(), row["CHECKSUM"])
            self.assertEqual(generate_blobs(root, 0, 1110), [])
            self.assertEqual(list((root / "documents/FILE_OBJECT_BLOBS").iterdir()), [])
