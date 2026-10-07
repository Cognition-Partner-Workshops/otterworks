import sys
from pathlib import Path

PYJOBS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PYJOBS))
sys.path.insert(0, str(Path(__file__).resolve().parent))
