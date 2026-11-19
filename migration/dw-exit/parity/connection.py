
import sys as _run_sys
from pathlib import Path as _RunPath
_run_sys.path.insert(0, str(_RunPath(__file__).resolve().parents[3]))
from warehouse.run_config import render as _run_render

import json
import os
import re
from pathlib import Path
import sys
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'warehouse/snowflake'))
from sfx_conn import query_tag

COMMENT = _run_render('run_token=__RUN_TOKEN__ expires=2026-11-24')
DATABASE = _run_render('__RUN_DATABASE__')


def validate_date(value):
    if not re.fullmatch(r'[0-9]{8}', value):
        raise ValueError('Business date must be YYYYMMDD')
    datetime.strptime(value, '%Y%m%d')
    return value


def connect(step, workload='PARITY'):
    import snowflake.connector
    from cryptography.hazmat.primitives import serialization

    key = serialization.load_pem_private_key(
        os.environ['SNOWFLAKE_PRIVATE_KEY'].encode(), password=None)
    return snowflake.connector.connect(
        account=os.environ['SNOWFLAKE_ACCOUNT'], user=os.environ['SNOWFLAKE_USER'],
        role=os.environ['SNOWFLAKE_ROLE'], database=DATABASE,
        warehouse=_run_render(f'__RUN_DATABASE___{workload}_WH'),
        paramstyle='qmark',
        private_key=key.private_bytes(serialization.Encoding.DER,
                                    serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption()),
        session_parameters={'QUERY_TAG': query_tag(workload.lower(), 'prove',
            {'run': _run_render('__RUN_TOKEN__'), 'act': 'prove', 'step': step}),
            'CLIENT_STAGE_ARRAY_BINDING_THRESHOLD': 0,
            'TIMEZONE': 'UTC', 'DATE_OUTPUT_FORMAT': 'YYYY-MM-DD',
            'TIMESTAMP_NTZ_OUTPUT_FORMAT': 'YYYY-MM-DD HH24:MI:SS.FF9'},
    )
