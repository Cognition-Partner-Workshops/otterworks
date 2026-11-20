"""Run the local BTEQ chain, PowerCenter daily load, then refresh close exports."""
import argparse
import os
from pathlib import Path
import runpy
import subprocess
import sys
import zlib

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from duckdb_close import business_day


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--business-date', default='20261109')
    parser.add_argument('--rows', type=int, default=2000)
    parser.add_argument('--seed', type=int, default=1110)
    parser.add_argument('--output', type=Path, default=ROOT / 'warehouse/exports')
    args = parser.parse_args()
    business_day(args.business_date)
    ns = os.environ.get('NS', 'sfg1120-before')
    env = dict(os.environ, NS=ns, PYTHONPATH=str(ROOT / 'warehouse/teradata'))
    env.setdefault('TD_PG_PORT', str(54500 + zlib.crc32(ns.encode()) % 1000))
    args.output.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, str(ROOT / 'warehouse/teradata/jobs/daily_chain'),
                    '--rows', str(args.rows), '--seed', str(args.seed),
                    '--business-date', args.business_date, '--exports', str(args.output.resolve())],
                   cwd=ROOT, env=env, check=True)
    infa = ROOT / 'etl/informatica'
    interpreter = infa / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    params = args.output.resolve() / 'billing-close.par'
    params.write_text('[Global]\n$$LOAD_DATE=' + args.business_date + '\n', encoding='utf-8')
    pc_env = dict(env, TD_PORT=env['TD_PG_PORT'], LANDING_DIR=str(ROOT / 'warehouse/landing'),
                  MAPPINGS='all', PMROOTDIR=str(infa / 'infa_shared' / ns))
    pc_env.pop('PYTHONPATH', None)
    subprocess.run([str(interpreter), '-m', 'runner', 'startworkflow', '-f', 'SFX_BILLING',
                    '-paramfile', str(params), 'wf_SFX_BILLING_DAILY'], cwd=infa, env=pc_env, check=True)
    variables = runpy.run_path(str(ROOT / 'warehouse/teradata/jobs/daily_chain'))['variables']
    env.update(variables(args.business_date, args.output))
    for script in ['documents/10_storage_monthly', 'billing/12_invoice_monthly', 'billing/13_period_close']:
        subprocess.run([sys.executable, '-m', 'bteq', 'run',
                        str(ROOT / 'warehouse/teradata/scripts' / (script + '.bteq'))],
                       cwd=ROOT, env=env, check=True)
    print('Legacy close complete: ' + str(args.output.resolve()))


if __name__ == '__main__':
    main()
