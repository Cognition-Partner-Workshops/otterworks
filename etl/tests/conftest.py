import sys
from pathlib import Path

# The ETL scripts run from etl/scripts (see run.sh) and import etl_config as a sibling module.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
