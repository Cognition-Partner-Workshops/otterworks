from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from warehouse.run_config import RunConfig


def before_namespace():
    return RunConfig.from_env().before_namespace
