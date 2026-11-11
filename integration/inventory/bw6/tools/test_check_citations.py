import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from check_citations import Checker


class CheckerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()
        (self.root / 'integration').mkdir()
        (self.root / 'integration/source.txt').write_text('first\nsecond\n')
        self.source = self.root / 'spec.md'
        self.checker = Checker(self.root)
        self.output = io.StringIO()
        self.capture = contextlib.redirect_stdout(self.output)
        self.capture.__enter__()
        self.addCleanup(self.capture.__exit__, None, None, None)

    def test_markdown_normal(self):
        self.checker.markdown(self.source, '\n'.join([
            '[`integration/source.txt:L1-L2`](integration/source.txt#L1-L2)',
            '`integration/source.txt:L1,L2` integration/source.txt:L2',
            '[web](https://example.com) [mail](mailto:x@y) [anchor](#section)',
        ]))
        self.assertEqual(self.checker.links, 1)
        self.assertEqual(self.checker.citations, 3)
        self.assertEqual(self.checker.failures, 0)

    def test_empty_inventory(self):
        self.assertEqual(self.checker.run(self.root), 0)
        self.assertIn('checked 0 links, 0 citations across 0 files: 0 failures', self.output.getvalue())

    def test_markdown_errors(self):
        self.checker.markdown(self.source, '\n'.join([
            '[missing](missing.txt)',
            '[zero](integration/source.txt#L0)',
            '[reverse](integration/source.txt#L2-L1)',
            '[long](integration/source.txt#L3)',
            '[`integration/other.txt:L1`](integration/source.txt#L2)',
            'integration/source.txt:L1,L4',
        ]))
        self.assertEqual(self.checker.failures, 8)
        self.assertIn('spec.md:1: missing file:', self.output.getvalue())
        self.assertIn('spec.md:6: invalid line range', self.output.getvalue())

    def test_json_nested_values_and_locations(self):
        self.checker.json(self.root / 'spec.json', '{\n "integration/missing:L1": ["integration/source.txt:L1,L2",\n {"nested": "integration/source.txt:L3"}]}')
        self.assertEqual(self.checker.citations, 2)
        self.assertEqual(self.checker.failures, 1)
        self.assertIn('spec.json:3: invalid line range', self.output.getvalue())

    def test_invalid_json(self):
        self.checker.json(self.root / 'spec.json', '{')
        self.assertEqual(self.checker.failures, 1)
        self.assertIn('invalid JSON:', self.output.getvalue())


if __name__ == '__main__':
    unittest.main()
