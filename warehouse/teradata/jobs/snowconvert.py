import argparse
import datetime as dt
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bteq.parser import commands


INSTALL_DOCS = 'https://docs.snowflake.com/en/en/migrations/snowconvert-docs/general/user-guide/snowconvert/command-line-interface/README'


def prepare_input(destination):
    paths = sorted((ROOT / 'ddl').glob('*/*.sql'))
    paths += sorted((ROOT / 'macros').glob('*.sql')) + sorted((ROOT / 'procedures').glob('*.sql'))
    paths.append(ROOT / 'dbql/schema.sql')
    count = 0
    for path in paths:
        for index, statement in enumerate(commands(path.read_text())):
            target = destination / path.relative_to(ROOT).parent / (path.stem+f'_{index:03d}.sql')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(statement+';\n')
            count += 1
    for path in sorted((ROOT / 'scripts').glob('*/*.bteq')) + sorted((ROOT / 'dbql').glob('*.bteq')):
        target = destination / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        count += 1
    return count


def convert(scai, namespace):
    executable = shutil.which(scai)
    if not executable:
        print(f'SnowConvert CLI not found: {scai}. Install scai using {INSTALL_DOCS}; set SCAI=/path/to/scai. It is not a PyPI package.', file=sys.stderr)
        return 2
    configuration = subprocess.run([sys.executable, str(ROOT / 'bin/snowflake_connection.py')])
    if configuration.returncode:
        return configuration.returncode
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = ROOT / '.snowconvert' / (stamp+'-'+namespace)
    output.mkdir(parents=True)
    source = output / 'input'
    count = prepare_input(source)
    print(f'SnowConvert input: {count} files; output: {output}', flush=True)
    project = output / 'project'
    with (output / 'command.log').open('w') as log:
        for arguments, cwd in [(['init', str(project), '-l', 'Teradata'], output),
                               (['code', 'add', '-i', str(source), '--code-already-split'], project),
                               (['code', 'convert', '--help'], project),
                               (['code', 'convert', '--scripttargetlanguage', 'SnowScript'], project)]:
            command = [executable, *arguments]
            log.write('$ '+shlex.join(command)+'\n')
            log.flush()
            environment = {key: value for key, value in os.environ.items() if key != 'SNOWFLAKE_PRIVATE_KEY'}
            environment['SNOWFLAKE_CONNECTION'] = 'sfx_d1110'
            result = subprocess.run(command, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, env=environment)
            log.write(f'EXIT {result.returncode}\n')
            log.flush()
            if result.returncode:
                print(f'SnowConvert exited {result.returncode}; see {output / "command.log"}', file=sys.stderr)
                return result.returncode
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scai', default='scai')
    parser.add_argument('--namespace', required=True)
    args = parser.parse_args()
    return convert(args.scai, args.namespace)


if __name__ == '__main__':
    sys.exit(main())
