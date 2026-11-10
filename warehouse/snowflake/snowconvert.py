"""Run SnowConvert in an isolated, ignored project; never deploy its output."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from runpy import run_path
import shutil
import subprocess

import tomlkit

from sfx_conn import ROOT


def secure_write(path, content):
    old = os.umask(0o077)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as handle:
            os.fchmod(handle.fileno(), 0o600)
            handle.write(content)
    finally:
        os.umask(old)


def configure_connection(home, env):
    values = {key.lower(): env['SNOWFLAKE_' + key]
              for key in ('ACCOUNT', 'USER', 'ROLE', 'WAREHOUSE', 'DATABASE')}
    key = env['SNOWFLAKE_PRIVATE_KEY']
    directory = home / '.snowflake'
    if directory.is_symlink():
        raise ValueError('Snowflake configuration directory must not be a symlink')
    directory.mkdir(mode=0o700, exist_ok=True)
    directory.chmod(0o700)
    config = directory / 'connections.toml'
    if config.is_symlink():
        raise ValueError('Snowflake configuration must not be a symlink')
    document = tomlkit.parse(config.read_text()) if config.exists() else tomlkit.document()
    key_file = directory / 'sfx_d1110.p8'
    values.update(authenticator='SNOWFLAKE_JWT', private_key_file=str(key_file))
    document['sfx_d1110'] = values
    secure_write(key_file, key)
    secure_write(config, tomlkit.dumps(document))


def inputs(repo):
    roots = [repo / 'warehouse/teradata', repo / 'etl/informatica']
    found = []
    for root in roots:
        suffixes = {'.sql', '.bteq', '.btq'} if root.name == 'teradata' else {'.xml'}
        if root.exists() and any(p.is_file() and p.suffix.lower() in suffixes and (
                root.name != 'teradata' or p.suffix.lower() != '.sql' or
                p.relative_to(root).parts[0] in {'ddl', 'macros', 'procedures'})
                for p in root.rglob('*')):
            found.append(root)
    return roots, found


def prepare_inputs(repo, output, found):
    split = run_path(str(ROOT.parent / 'teradata/bteq/parser.py'))['commands']
    prepared = []
    manifest = []
    for root in found:
        destination = output / 'input' / root.name
        destination.mkdir(parents=True)
        paths = sorted(root.rglob('*'))
        if root.name == 'teradata':
            paths = [p for p in paths if p.is_file() and (
                p.suffix.lower() in {'.bteq', '.btq'} or
                (p.suffix.lower() == '.sql' and p.relative_to(root).parts[0] in
                 {'ddl', 'macros', 'procedures'}))]
        else:
            paths = [p for p in paths if p.is_file() and p.suffix.lower() == '.xml']
            workflows = [p for p in paths if p.name.lower().startswith('wf_')]
            paths = workflows or paths
        for path in paths:
            target = destination / path.relative_to(root)
            target.parent.mkdir(parents=True, exist_ok=True)
            if path.suffix.lower() == '.sql':
                for index, statement in enumerate(split(path.read_text())):
                    target.with_name(f'{target.stem}_{index:03d}.sql').write_text(statement + ';\n')
            else:
                shutil.copyfile(path, target)
            manifest.append(str(path.relative_to(repo)))
        if paths:
            prepared.append((root.name, destination))
    (output / 'inputs.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return prepared


def run(repo, home, env):
    searched, found = inputs(repo)
    print('SnowConvert inputs searched: ' + ', '.join(str(p.relative_to(repo)) for p in searched))
    if not found:
        print('No SQL/BTEQ or Informatica XML input found; no conversion performed.')
    executable = shutil.which('scai', path=env.get('PATH'))
    if not executable:
        print('scai is not installed. Install the SnowConvert AI CLI from Snowflake (not PyPI), then retry.')
        return 2
    if not found:
        return 0
    try:
        configure_connection(home, env)
    except (KeyError, ValueError, OSError):
        print('SnowConvert credential configuration failed; check environment bindings and ~/.snowflake permissions.')
        return 2
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = repo / 'warehouse/snowconvert/raw' / stamp
    output.mkdir(parents=True, mode=0o700)
    prepared = prepare_inputs(repo, output, found)
    child_env = {k: v for k, v in env.items() if not k.startswith('SNOWFLAKE_')}
    child_env['SNOWFLAKE_CONNECTION'] = 'sfx_d1110'
    commands = []
    for area, source in prepared:
        project = output / (area + '_project')
        commands.append(([executable, 'init', str(project), '-l', 'Teradata', '-c', 'sfx_d1110'], output))
        add = [executable, 'code', 'add', '-i', str(source)]
        if area == 'teradata':
            add.append('--code-already-split')
        commands.append((add, project))
        commands.append(([executable, 'code', 'convert', '--show-ewis'], project))
    summary = []
    for index, (command, cwd) in enumerate(commands):
        result = subprocess.run(command, cwd=cwd, env=child_env, capture_output=True)
        combined = result.stdout + result.stderr
        secret = env['SNOWFLAKE_PRIVATE_KEY'].encode()
        if (secret and secret in combined) or re.search(rb'-----BEGIN [A-Z ]*PRIVATE KEY-----', combined):
            print('scai output contains private key material; raw output was not persisted.')
            return 2
        (output / f'{index:02d}.stdout').write_bytes(result.stdout)
        (output / f'{index:02d}.stderr').write_bytes(result.stderr)
        summary.append({'command': command[1:], 'cwd': str(cwd.relative_to(output)),
                        'exit_code': result.returncode})
        (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
        text = combined.decode(errors='replace').lower()
        key_auth = r'(key[- ]?pair|snowflake_jwt|private[-_ ]?key)'
        rejected = r'(unsupported|not supported|reject(?:ed|s)?|not accepted)'
        if re.search(key_auth + r'.*?' + rejected + '|' + rejected + r'.*?' + key_auth, text, re.S):
            print('scai rejected key-pair auth; stopping without password fallback.')
            return 2
        if result.returncode:
            print(f'scai failed with exit {result.returncode}; unmodified output: {output.relative_to(repo)}')
            return result.returncode
    print(f'SnowConvert complete; unmodified output and summary: {output.relative_to(repo)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(run(ROOT.parents[1], Path.home(), os.environ.copy()))
