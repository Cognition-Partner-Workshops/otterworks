"""Source ranges for DBC parity evidence."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BRANCH = 'devin/sfg1120-dbc'


def link(path, start=1, end=None):
    path = Path(path)
    end = end or max(1, len((ROOT / path).read_text().splitlines()))
    base = 'https://github.com/Cognition-Partner-Workshops/otterworks/blob/' + BRANCH + '/'
    return {'file': path.as_posix(), 'start_line': start, 'end_line': end,
            'url': f'{base}{path.as_posix()}#L{start}-L{end}'}
