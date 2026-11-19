
import sys as _run_sys
from pathlib import Path as _RunPath
_run_sys.path.insert(0, str(_RunPath(__file__).resolve().parents[3]))
from warehouse.run_config import render as _run_render

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
            td.run(_run_render((SQL / 'supplemental_source.sql').read_text()))
            assert td.errorcode == 0, td.output.getvalue()
            for name in ('FEED', 'VERSIONS', 'SET_ROWS', 'MULTISET_ROWS', 'TRUNCATION', 'QUALIFY_TIES'):
                source = 'sfx_probes.' + name.lower()
                upload(sf, 'PROBE_' + name, [(n, snow_type(t)) for n, t in td.columns(source)],
                       source_rows(td.conn, 'sfx_probes', name.lower()))
        with sf.cursor() as cursor:
            cursor.execute(_run_render('CREATE SCHEMA IF NOT EXISTS __RUN_DATABASE__.BILLING_PROBES COMMENT = ?'), (COMMENT,))
            for name in ('FEED', 'VERSIONS'):
                cursor.execute('CREATE OR REPLACE TABLE IDENTIFIER(?) CLONE IDENTIFIER(?) COMMENT = ?',
                               (_run_render(f'__RUN_DATABASE__.BILLING_PROBES.{name}'), _run_render(f'__RUN_DATABASE__.TD_BASELINE.PROBE_{name}'), COMMENT))
            path = SQL / ('supplemental_initial.sql' if initial else 'supplemental.sql')
            for statement in commands(_run_render(path.read_text())):
                cursor.execute(statement)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--capture', action='store_true')
    parser.add_argument('--initial', action='store_true')
    args = parser.parse_args()
    run(args.capture, args.initial)
