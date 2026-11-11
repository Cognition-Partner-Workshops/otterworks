import argparse
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from capture import Runner, snow_type, source_rows, upload
from deploy import commands
from parity.connection import COMMENT, connect

SQL = Path(__file__).resolve().parent


def run(capture, initial):
    with Runner(output=io.StringIO()) as td, connect('supplemental_initial' if initial else 'supplemental_fixed') as sf:
        if capture:
            td.run((SQL / 'supplemental_source.sql').read_text())
            assert td.errorcode == 0, td.output.getvalue()
            for name in ('FEED', 'VERSIONS', 'SET_ROWS', 'MULTISET_ROWS', 'TRUNCATION', 'QUALIFY_TIES'):
                source = 'sfx_probes.' + name.lower()
                upload(sf, 'PROBE_' + name, [(n, snow_type(t)) for n, t in td.columns(source)],
                       source_rows(td.conn, 'sfx_probes', name.lower()))
        with sf.cursor() as cursor:
            cursor.execute('CREATE SCHEMA IF NOT EXISTS SFX_D1110_AFTER.BILLING_PROBES COMMENT = ?', (COMMENT,))
            for name in ('FEED', 'VERSIONS'):
                cursor.execute('CREATE OR REPLACE TABLE IDENTIFIER(?) CLONE IDENTIFIER(?) COMMENT = ?',
                               (f'SFX_D1110_AFTER.BILLING_PROBES.{name}', f'SFX_D1110_AFTER.TD_BASELINE.PROBE_{name}', COMMENT))
            path = SQL / ('supplemental_initial.sql' if initial else 'supplemental.sql')
            for statement in commands(path.read_text()):
                cursor.execute(statement)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--capture', action='store_true')
    parser.add_argument('--initial', action='store_true')
    args = parser.parse_args()
    run(args.capture, args.initial)
