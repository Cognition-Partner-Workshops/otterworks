import json
import os
import re
from datetime import datetime

COMMENT = 'run_token=sfx-d1110 expires=2026-11-24'
DATABASE = 'SFX_D1110_AFTER'


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
        warehouse=f'SFX_D1110_{workload}_WH',
        paramstyle='qmark',
        private_key=key.private_bytes(serialization.Encoding.DER,
                                    serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption()),
        session_parameters={'QUERY_TAG': json.dumps(
            {'run': 'sfx-d1110', 'act': 'prove', 'step': step}),
            'CLIENT_STAGE_ARRAY_BINDING_THRESHOLD': 0,
            'TIMEZONE': 'UTC', 'DATE_OUTPUT_FORMAT': 'YYYY-MM-DD',
            'TIMESTAMP_NTZ_OUTPUT_FORMAT': 'YYYY-MM-DD HH24:MI:SS.FF9'},
    )
