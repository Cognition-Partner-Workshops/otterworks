"""Attribution shared by connector, named-profile and dbt sessions."""
import json
import os
from pathlib import Path
import subprocess
import uuid

from warehouse.run_config import RunConfig

RUN_ID = str(uuid.uuid4())


def query_tag(workload, phase, extra=None):
    if not workload or not phase:
        raise ValueError('Workload and phase are required')
    commit = os.getenv('SFX_COMMIT') or subprocess.check_output(
        ['git', 'rev-parse', '--short', 'HEAD'], cwd=Path(__file__).resolve().parent,
        text=True).strip()
    values = dict(extra or {})
    if os.getenv('SFX_QUERY_TAG_LABEL'):
        values['tag'] = os.environ['SFX_QUERY_TAG_LABEL']
    values.update(workload=workload, phase=phase, commit=commit,
                  run_id=os.getenv('SFX_RUN_ID') or RUN_ID,
                  run_token=RunConfig.from_env().token)
    return json.dumps(values, separators=(',', ':'))
