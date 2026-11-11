import os
from pathlib import Path
import re
import sys
import tempfile


FIELDS = ('ACCOUNT', 'USER', 'ROLE', 'WAREHOUSE', 'DATABASE')
REQUIRED = tuple('SNOWFLAKE_'+name for name in FIELDS) + ('SNOWFLAKE_PRIVATE_KEY',)


def quote(value):
    escapes = {'"': '\\"', '\\': '\\\\', '\b': '\\b', '\t': '\\t', '\n': '\\n', '\f': '\\f', '\r': '\\r'}
    result = []
    for char in value:
        if 0xD800 <= ord(char) <= 0xDFFF:
            raise ValueError('Invalid Unicode')
        result.append(escapes.get(char, f'\\u{ord(char):04X}' if ord(char)<32 or ord(char)==127 else char))
    return '"'+''.join(result)+'"'


def headers(text):
    multiline, offset = None, 0
    for line in text.splitlines(keepends=True):
        if multiline is None:
            match = re.fullmatch(r'\s*\[(.+?)\][ \t]*(?:#[^\r\n]*)?[\r\n]*', line)
            if match:
                yield offset, match[1].strip()
        index = 0
        while index < len(line):
            if multiline:
                if line.startswith(multiline, index):
                    index += 3
                    multiline = None
                elif multiline == '"""' and line[index] == '\\':
                    index += 2
                else:
                    index += 1
            elif line[index] == '#':
                break
            elif line[index:index+3] in ('"""', "'''"):
                multiline = line[index:index+3]
                index += 3
            elif line[index] in ('"', "'"):
                delimiter = line[index]
                index += 1
                while index < len(line):
                    if line[index] == delimiter:
                        index += 1
                        break
                    index += 2 if delimiter == '"' and line[index] == '\\' else 1
            else:
                index += 1
        offset += len(line)


def update(text, section):
    positions = list(headers(text))
    matches = [index for index, (_, name) in enumerate(positions)
               if name in ('sfx_d1110', '"sfx_d1110"', "'sfx_d1110'")]
    if len(matches) > 1:
        raise ValueError('Duplicate connection table')
    if not matches:
        return text+('' if not text or text.endswith('\n') else '\n')+'\n'+section
    index = matches[0]
    start = positions[index][0]
    end = positions[index+1][0] if index+1<len(positions) else len(text)
    return text[:start]+section+text[end:]


def configure():
    missing = [name for name in REQUIRED if not os.environ.get(name, '').strip()]
    if missing:
        print('Missing environment variables: '+', '.join(missing), file=sys.stderr)
        return 2
    home = Path.home().resolve()
    repository = Path(__file__).resolve().parents[3]
    if home == repository or repository in home.parents:
        raise ValueError('HOME must be outside repository')
    directory = home / '.snowflake'
    connection = directory / 'connections.toml'
    key = directory / 'sfx_d1110.p8'
    section = '[sfx_d1110]\n'+''.join(name.lower()+' = '+quote(os.environ['SNOWFLAKE_'+name])+'\n' for name in FIELDS)
    section += 'authenticator = "SNOWFLAKE_JWT"\nprivate_key_file = '+quote(str(key))+'\n\n'
    if os.environ.get('SNOWFLAKE_QUERY_TAG'):
        section += 'session_parameters = { QUERY_TAG = '+quote(os.environ['SNOWFLAKE_QUERY_TAG'])+' }\n\n'
    previous_mask = os.umask(0o077)
    temporary = []
    try:
        if directory.is_symlink() or connection.is_symlink() or key.is_symlink():
            raise ValueError('Configuration must not use symlinks')
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        directory.chmod(0o700)
        existing = connection.read_bytes().decode('utf-8') if connection.exists() else ''
        contents = update(existing, section)
        for target, value in ((key, os.environ['SNOWFLAKE_PRIVATE_KEY']), (connection, contents)):
            descriptor, name = tempfile.mkstemp(prefix='.sfx-d1110-', dir=directory)
            temporary.append(Path(name))
            with os.fdopen(descriptor, 'wb') as handle:
                handle.write(value.encode('utf-8'))
            os.replace(name, target)
            target.chmod(0o600)
    finally:
        for path in temporary:
            path.unlink(missing_ok=True)
        os.umask(previous_mask)
    return 0


def main():
    try:
        return configure()
    except (OSError, ValueError, UnicodeError):
        print('Unable to update Snowflake configuration.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
