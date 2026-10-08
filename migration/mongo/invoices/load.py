"""Load unit invoices (batch w1-b04) per .migration/mapping_spec.json map-v3."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.loader import main  # noqa: E402

if __name__ == "__main__":
    main(str(Path(__file__).with_name("unit.json")))
