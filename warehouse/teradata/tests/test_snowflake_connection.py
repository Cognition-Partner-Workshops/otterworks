import os
from pathlib import Path
import stat
import subprocess
import sys

try:
    import tomllib
except ImportError:
    tomllib = None


SCRIPT = Path(__file__).resolve().parents[1] / 'bin/snowflake_connection.py'


def environment(home):
    values = {key: value for key, value in os.environ.items() if not key.startswith('SNOWFLAKE_')}
    values.update(HOME=str(home), SNOWFLAKE_ACCOUNT='example-account', SNOWFLAKE_USER='example-user',
                  SNOWFLAKE_ROLE='example-role', SNOWFLAKE_WAREHOUSE='example-warehouse',
                  SNOWFLAKE_DATABASE='example-database', SNOWFLAKE_PRIVATE_KEY='test-only key material\n')
    return values


def invoke(values):
    return subprocess.run([sys.executable, str(SCRIPT)], env=values, capture_output=True, text=True)


def test_connection_creation_and_update(tmp_path):
    directory = tmp_path/'.snowflake'
    directory.mkdir(mode=0o755)
    before = '[other]\naccount = "keep"\nnotes = """\n[sfx_d1110]\n"""\n\n'
    (directory/'connections.toml').write_text(before)
    values = environment(tmp_path)
    values['SNOWFLAKE_USER'] = 'quote" slash\\ tab\t line\n control\x01 del\x7f snowman☃ emoji🌲'
    result = invoke(values)
    assert (result.returncode, result.stdout, result.stderr) == (0, '', '')
    contents = (directory/'connections.toml').read_text()
    assert contents.startswith(before)
    assert 'user = "quote\\" slash\\\\ tab\\t line\\n control\\u0001 del\\u007F snowman☃ emoji🌲"' in contents
    assert 'authenticator = "SNOWFLAKE_JWT"' in contents
    assert 'private_key_file = "'+str(directory/'sfx_d1110.p8')+'"' in contents
    assert (directory/'sfx_d1110.p8').read_text() == values['SNOWFLAKE_PRIVATE_KEY']
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert all(stat.S_IMODE((directory/name).stat().st_mode) == 0o600 for name in ('connections.toml', 'sfx_d1110.p8'))
    (directory/'connections.toml').write_text(contents+'[after]\nuser = "also-keep"\n')
    values['SNOWFLAKE_ROLE'] = 'updated-example-role'
    result = invoke(values)
    assert (result.returncode, result.stdout, result.stderr) == (0, '', '')
    contents = (directory/'connections.toml').read_text()
    assert contents.startswith(before) and contents.endswith('[after]\nuser = "also-keep"\n')
    assert 'role = "updated-example-role"' in contents
    assert contents.count('authenticator = "SNOWFLAKE_JWT"') == 1
    if tomllib:
        parsed = tomllib.loads(contents)
        assert parsed['sfx_d1110']['user'] == values['SNOWFLAKE_USER']
    assert not list(directory.glob('.sfx-d1110-*'))


def test_missing_variables_are_names_only(tmp_path):
    values = environment(tmp_path)
    del values['SNOWFLAKE_PRIVATE_KEY']
    del values['SNOWFLAKE_USER']
    result = invoke(values)
    assert result.returncode == 2 and result.stdout == ''
    assert result.stderr == 'Missing environment variables: SNOWFLAKE_USER, SNOWFLAKE_PRIVATE_KEY\n'
    assert not (tmp_path/'.snowflake').exists()
    assert not any(value in result.stderr for key, value in values.items() if key.startswith('SNOWFLAKE_'))


def test_configuration_errors_do_not_echo_values(tmp_path):
    (tmp_path/'.snowflake').write_text('not a directory')
    values = environment(tmp_path)
    result = invoke(values)
    assert (result.returncode, result.stdout, result.stderr) == (2, '', 'Unable to update Snowflake configuration.\n')


def test_symlink_is_not_followed(tmp_path):
    directory = tmp_path/'.snowflake'
    directory.mkdir()
    outside = tmp_path/'unrelated'
    outside.write_text('unchanged')
    (directory/'connections.toml').symlink_to(outside)
    result = invoke(environment(tmp_path))
    assert result.returncode == 2
    assert outside.read_text() == 'unchanged'
