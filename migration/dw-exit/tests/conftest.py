import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import parity

for directory in (Path(__file__).resolve().parents[1] / 'parity',
                  Path(__file__).resolve().parents[3] / 'warehouse/parity'):
    if str(directory) not in parity.__path__:
        parity.__path__.append(str(directory))
