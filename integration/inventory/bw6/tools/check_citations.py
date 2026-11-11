"""Validate local Markdown links and repository line citations in the BW6 inventory."""

import json
import re
from collections import defaultdict, deque
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[4]
INVENTORY = ROOT / "integration/inventory/bw6"
LINK = re.compile(r"\[([^\]\n]*)\]\(\s*(<[^>\n]*>|(?:[^()\n]|\([^()\n]*\))*)\s*\)")
RANGE = r"L(-?\d+)(?:-L(-?\d+))?"
CITATION = re.compile(
    r"(?<![\w/])(?P<path>integration/[^\s`\[\]()<>,:]+):"
    r"(?P<ranges>L-?\d+(?:-L-?\d+)?(?:,\s*L-?\d+(?:-L-?\d+)?)*)"
)
ANCHOR = re.compile(RANGE)
LABEL = re.compile(r"(?P<path>[^`]+):(?P<ranges>" + RANGE + r")")
JSON_STRING = re.compile(r'"(?:[^"\\]|\\.)*"')


def string_values(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from string_values(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from string_values(item)


class Checker:
    def __init__(self, root=ROOT):
        self.root = root
        self.links = 0
        self.citations = 0
        self.failures = 0
        self.line_counts = {}

    def fail(self, source, line, message):
        self.failures += 1
        print(f"{source.relative_to(self.root)}:{line}: {message}")

    def check_file(self, source, line, target):
        if not target.is_file():
            self.fail(source, line, f"missing file: {target.relative_to(self.root) if target.is_relative_to(self.root) else target}")
            return False
        return True

    def check_range(self, source, line, target, start, end):
        if target not in self.line_counts:
            self.line_counts[target] = len(target.read_bytes().splitlines())
        count = self.line_counts[target]
        if start < 1 or end < start or end > count:
            self.fail(source, line, f"invalid line range L{start}-L{end} for {target.relative_to(self.root) if target.is_relative_to(self.root) else target} ({count} lines)")

    def scan_citations(self, source, text, offset=0):
        for match in CITATION.finditer(text):
            self.citations += 1
            line = offset + text.count("\n", 0, match.start()) + 1
            target = (self.root / match['path']).resolve()
            if self.check_file(source, line, target):
                for part in re.finditer(RANGE, match['ranges']):
                    start = int(part[1])
                    end = int(part[2]) if part[2] is not None else start
                    self.check_range(source, line, target, start, end)

    def markdown(self, source, text):
        for match in LINK.finditer(text):
            label, destination = match.groups()
            destination = destination.strip()
            if destination.startswith('<'):
                destination = destination[1:destination.index('>')]
            else:
                destination = re.split(r'\s+["\']', destination, maxsplit=1)[0]
            parsed = urlsplit(destination)
            if parsed.scheme.lower() in {'http', 'https', 'mailto'} or destination.startswith('#'):
                continue
            self.links += 1
            line = text.count('\n', 0, match.start()) + 1
            target = (source.parent / unquote(parsed.path)).resolve()
            exists = self.check_file(source, line, target)
            anchor = ANCHOR.fullmatch(unquote(parsed.fragment))
            if anchor:
                start = int(anchor[1])
                end = int(anchor[2]) if anchor[2] is not None else start
                if exists:
                    self.check_range(source, line, target, start, end)
            citation = LABEL.fullmatch(label[1:-1]) if label.startswith('`') and label.endswith('`') else None
            if citation:
                if (self.root / citation['path']).resolve() != target:
                    self.fail(source, line, 'citation label path differs from link target')
                label_range = ANCHOR.fullmatch(citation['ranges'])
                if not anchor or not label_range or (
                    int(label_range[1]), int(label_range[2] or label_range[1])
                ) != (int(anchor[1]), int(anchor[2] or anchor[1])):
                    self.fail(source, line, 'citation label line range differs from link anchor')
        self.scan_citations(source, text)

    def json(self, source, text):
        try:
            value = json.loads(text)
        except json.JSONDecodeError as error:
            self.fail(source, error.lineno, f'invalid JSON: {error.msg}')
            return
        locations = defaultdict(deque)
        for match in JSON_STRING.finditer(text):
            if not text[match.end():].lstrip().startswith(':'):
                locations[json.loads(match[0])].append(text.count('\n', 0, match.start()))
        for value in string_values(value):
            offset = locations[value].popleft()
            # Decoded newlines belong to the same JSON string token, not new source lines.
            for match in CITATION.finditer(value):
                self.scan_citations(source, match[0], offset)

    def run(self, inventory=INVENTORY):
        files = sorted(path for path in inventory.rglob('*') if path.suffix in {'.md', '.json'} and path.is_file())
        for source in files:
            text = source.read_text(encoding='utf-8')
            if source.suffix == '.md':
                self.markdown(source, text)
            else:
                self.json(source, text)
        print(f'checked {self.links} links, {self.citations} citations across {len(files)} files: {self.failures} failures')
        return int(bool(self.failures))


if __name__ == '__main__':
    raise SystemExit(Checker().run())
